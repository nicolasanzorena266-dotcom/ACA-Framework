from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from aca_kernel.core.state import CognitiveState
from aca_os.event_bus import EventBus
from aca_os.execution_trace import ExecutionTrace, sanitize
from aca_os.runtime_timeline import RuntimeTimeline


@dataclass(frozen=True)
class RuntimeComponentSnapshot:
    """Static runtime component inventory for inspector clients."""

    name: str
    class_name: str
    role: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "class_name": self.class_name,
            "role": self.role,
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
        roles = {
            "conversation_manager": "conversation lifecycle",
            "intent_matcher": "zero-cost intent detection",
            "action_planner": "zero-cost action selection",
            "flow_router": "zero-cost flow routing",
            "policy_manager": "policy decisioning",
            "tool_engine": "tool execution",
            "memory_engine": "memory consolidation",
            "context_manager": "context assembly",
            "event_bus": "internal event publication",
        }
        return [
            RuntimeComponentSnapshot(
                name=name,
                class_name=getattr(getattr(self.runtime, name), "__class__").__name__,
                role=role,
            )
            for name, role in roles.items()
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
            metrics={
                "trace_count": len(getattr(self.runtime, "_traces", {})),
                "timeline_entries": len(timeline.get("entries", [])) if timeline else 0,
                "runtime_event_count": len(events),
                "last_trace_duration_ms": trace.duration_ms if trace else None,
            },
        )

    def inspect_trace(self, trace_id: str | None = None) -> Dict[str, Any]:
        trace = self.runtime.last_trace() if trace_id is None else self.runtime.trace(trace_id)
        if trace is None:
            raise ValueError("No execution trace available.")
        return trace.to_dict()

    def inspect_timeline(self, state: CognitiveState) -> Dict[str, Any]:
        return RuntimeTimeline.from_state(state, self.runtime.event_bus.events()).to_dict()



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
        "fact_keys": sorted(state.facts.keys()),
    }



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
    }
