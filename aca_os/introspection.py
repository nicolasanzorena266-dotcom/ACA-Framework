from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from aca_kernel.core.state import CognitiveState
from aca_os.event_bus import EventBus
from aca_os.execution_trace import ExecutionTrace, sanitize
from aca_os.runtime_timeline import RuntimeTimeline
from aca_os.component_registry import ComponentDescriptor


@dataclass(frozen=True)
class RuntimeComponentSnapshot:
    """Static runtime component inventory for inspector clients."""

    name: str
    class_name: str
    role: str
    version: str = "0.1.0"
    provider: str = "aca"
    capabilities: List[str] = field(default_factory=list)
    state: str = "registered"

    @classmethod
    def from_descriptor(cls, descriptor: ComponentDescriptor) -> "RuntimeComponentSnapshot":
        return cls(
            name=descriptor.name,
            class_name=descriptor.class_name,
            role=descriptor.role,
            version=descriptor.version,
            provider=descriptor.provider,
            capabilities=list(descriptor.capabilities),
            state=descriptor.state.value,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "class_name": self.class_name,
            "role": self.role,
            "version": self.version,
            "provider": self.provider,
            "capabilities": list(self.capabilities),
            "state": self.state,
        }


@dataclass(frozen=True)
class RuntimeIntrospectionSnapshot:
    """Stable read-only contract for CLI, Studio, REST and future inspectors."""

    runtime_id: str
    status: str
    components: List[RuntimeComponentSnapshot] = field(default_factory=list)
    last_state: Dict[str, Any] = field(default_factory=dict)
    last_trace: Dict[str, Any] = field(default_factory=dict)
    timeline: Dict[str, Any] = field(default_factory=dict)
    event_bus: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    component_registry: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime_id": self.runtime_id,
            "status": self.status,
            "components": [component.to_dict() for component in self.components],
            "last_state": sanitize(self.last_state),
            "last_trace": sanitize(self.last_trace),
            "timeline": sanitize(self.timeline),
            "event_bus": sanitize(self.event_bus),
            "metrics": sanitize(self.metrics),
            "component_registry": sanitize(self.component_registry),
        }


class RuntimeIntrospectionAPI:
    """Runtime-facing introspection API.

    This object is intentionally read-only. It normalizes existing runtime
    observability data so UI, CLI and future transport layers do not depend on
    private runtime internals.
    """

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    def component_inventory(self) -> List[RuntimeComponentSnapshot]:
        return [
            RuntimeComponentSnapshot.from_descriptor(descriptor)
            for descriptor in self.runtime.component_registry.list()
        ]

    def snapshot(
        self,
        *,
        state: CognitiveState | None = None,
        trace: ExecutionTrace | None = None,
        event_bus: EventBus | None = None,
    ) -> RuntimeIntrospectionSnapshot:
        trace = trace if trace is not None else self.runtime.last_trace()
        events = (event_bus or self.runtime.event_bus).events()
        timeline = RuntimeTimeline.from_state(state, events).to_dict() if state else {}

        metrics = self.runtime.metrics_engine.snapshot(runtime_id=self.runtime.runtime_id).to_dict()
        metrics.update(
            {
                "timeline_entries": len(timeline.get("entries", [])) if timeline else 0,
                "runtime_event_count": len(events),
                "last_trace_duration_ms": trace.duration_ms if trace else None,
            }
        )

        return RuntimeIntrospectionSnapshot(
            runtime_id=self.runtime.runtime_id,
            status="ready",
            components=self.component_inventory(),
            last_state=_state_summary(state),
            last_trace=_trace_summary(trace),
            timeline=timeline,
            event_bus={
                "event_count": len(events),
                "event_types": [event.type for event in events],
                "events": [event.to_dict() for event in events],
            },
            metrics=metrics,
            component_registry=self.runtime.component_registry.snapshot(),
        )

    def inspect_trace(self, trace_id: str | None = None) -> Dict[str, Any]:
        trace = self.runtime.last_trace() if trace_id is None else self.runtime.trace(trace_id)
        if trace is None:
            raise ValueError("No execution trace available.")
        return trace.to_dict()

    def inspect_timeline(self, state: CognitiveState) -> Dict[str, Any]:
        return RuntimeTimeline.from_state(state, self.runtime.event_bus.events()).to_dict()

    def inspect_authority_graph(self, artifact: str | None = None) -> Dict[str, Any]:
        """Build the passive SA-3.1 authority graph from source and the last trace."""
        from aca_os.authority_dependency_graph import build_authority_dependency_graph

        trace = self.runtime.last_trace()
        graph = build_authority_dependency_graph(
            runtime_trace=trace.to_dict() if trace is not None else None,
        )
        if artifact is not None:
            return graph.inspect_artifact(artifact)
        return graph.to_dict()



def _state_summary(state: CognitiveState | None) -> Dict[str, Any]:
    if state is None:
        return {}
    return {
        "conversation_id": state.conversation_id,
        "version": state.version,
        "response": state.response,
        "selected_program": state.selected_program,
        "intent": (state.intent_match or {}).get("intent"),
        "policy_decision": (state.policy_result or {}).get("decision"),
        "decision_graph": state.facts.get("zero_cost_decision_graph", {}),
        "action_plan": state.facts.get("zero_cost_action_plan", {}),
        "execution_flow": state.facts.get("zero_cost_execution_flow", {}),
        "execution_plan": state.facts.get("zero_cost_execution_plan", {}),
        "runtime_execution_engine": state.facts.get("runtime_execution_engine", {}),
        "conversation_state_runtime": state.facts.get("conversation_state_runtime", {}),
        "runtime_executor_shadow": state.facts.get("runtime_executor_shadow", {}),
        "tool_executions": _tool_execution_summary(state),
        "output_decision": _output_decision_summary(state),
        "fact_keys": sorted(state.facts.keys()),
    }


def _output_decision_summary(state: CognitiveState) -> Dict[str, Any]:
    """Reconstruct why the visible response is what it is.

    ExecutionStepOutcome for the "output" step already records the Composer
    decision, the Conversational-First authority selection (with rollback
    reason when it fell back) and the LLM verbalization outcome, but nothing
    surfaced it above `execution_step_outcomes` -- a turn could not be fully
    audited from `_state_summary`/`_trace_summary` alone (ACA-303).
    """
    for outcome in state.facts.get("execution_step_outcomes", []):
        if not isinstance(outcome, dict) or outcome.get("step") != "output":
            continue
        result = outcome.get("result", {})
        if not isinstance(result, dict):
            continue
        return {
            "composer_changed_response": result.get("changed"),
            "composer_reason": result.get("reason"),
            "conversation_authority": result.get("conversation_authority", {}),
            "llm_verbalization": result.get("llm_verbalization", {}),
        }
    return {}


def _tool_execution_summary(state: CognitiveState) -> list[Dict[str, Any]]:
    executions = []
    for outcome in state.facts.get("execution_step_outcomes", []):
        if not isinstance(outcome, dict):
            continue
        result = outcome.get("result", {})
        if not isinstance(result, dict):
            continue
        execution = result.get("tool_execution")
        if isinstance(execution, dict) and execution:
            contract = execution.get("execution_contract", {})
            executions.append(
                {
                    "tool_name": execution.get("tool_name"),
                    "mode": execution.get("mode"),
                    "origin": execution.get("origin"),
                    "runtime_engine": execution.get("runtime_engine"),
                    "owner": execution.get("owner"),
                    "action": execution.get("action"),
                    "executed": execution.get("executed"),
                    "reason": execution.get("reason"),
                    "deterministic": contract.get("deterministic") if isinstance(contract, dict) else None,
                    "has_side_effects": contract.get("has_side_effects") if isinstance(contract, dict) else None,
                    "supports_dry_run": contract.get("supports_dry_run") if isinstance(contract, dict) else None,
                    "supports_replay": contract.get("supports_replay") if isinstance(contract, dict) else None,
                    "supports_shadow": contract.get("supports_shadow") if isinstance(contract, dict) else None,
                    "idempotency": contract.get("idempotency") if isinstance(contract, dict) else None,
                }
            )
    return executions



def _trace_summary(trace: ExecutionTrace | None) -> Dict[str, Any]:
    if trace is None:
        return {}
    return {
        "trace_id": trace.trace_id,
        "conversation_id": trace.conversation_id,
        "runtime_id": trace.runtime_id,
        "started_at": trace.started_at,
        "finished_at": trace.finished_at,
        "duration_ms": trace.duration_ms,
        "event_count": len(trace.events),
        "operations": trace.operations(),
        "semantic_authority": dict(trace.semantic_authority),
        "semantic_projection": dict(trace.semantic_projection),
        "semantic_authority_pilot": dict(trace.semantic_authority_pilot),
        "conversational_goal_authority": dict(
            trace.conversational_goal_authority
        ),
    }
