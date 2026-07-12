from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.conversation_state import ConversationState
from aca_os.policy_manager import PolicyDecision, PolicyResult
from aca_os.step_handlers import (
    StepExecutionContext,
    StepHandlerRegistry,
    StepRuntimeServices,
    plan_has_step,
    step_from_plan,
)
from aca_os.tool_engine import ToolExecutionMode
from zero_cost.execution_plan import ExecutionPlan


@dataclass(frozen=True)
class RuntimeExecutorResult:
    contract: str = "runtime_executor_shadow_result.v1"
    mode: str = "shadow"
    outcomes: List[Dict[str, Any]] = field(default_factory=list)
    final_state: CognitiveState | None = None
    execution_plan: Dict[str, Any] = field(default_factory=dict)
    policy_result: Dict[str, Any] = field(default_factory=dict)
    tool_evidence: Dict[str, Any] = field(default_factory=dict)
    selected_program: str | None = None
    response: str | None = None
    interrupted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "mode": self.mode,
            "outcomes": list(self.outcomes),
            "execution_plan": dict(self.execution_plan),
            "policy_result": dict(self.policy_result),
            "tool_evidence": dict(self.tool_evidence),
            "selected_program": self.selected_program,
            "response": self.response,
            "interrupted": self.interrupted,
        }


@dataclass(frozen=True)
class RuntimeExecutorComparison:
    contract: str = "runtime_executor_shadow_comparison.v1"
    equivalent: bool = False
    equivalence_score: float = 0.0
    official: Dict[str, Any] = field(default_factory=dict)
    shadow: Dict[str, Any] = field(default_factory=dict)
    divergences: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "equivalent": self.equivalent,
            "equivalence_score": self.equivalence_score,
            "official": dict(self.official),
            "shadow": dict(self.shadow),
            "divergences": [dict(divergence) for divergence in self.divergences],
        }


class RuntimeExecutor:
    """Plan-driven executor used in official and shadow modes.

    The executor walks `ExecutionPlan.steps` and delegates each step to the
    registered handler. During controlled adoption it owns migrated flows and
    also produces comparable projections for migration validation.
    """

    def __init__(self, *, handlers: StepHandlerRegistry, services: StepRuntimeServices, domain_context: Dict[str, Any] | None = None) -> None:
        self.handlers = handlers
        self.services = services
        self.domain_context = domain_context or {}

    def execute(
        self,
        *,
        event: Event,
        state: CognitiveState,
        execution_plan: ExecutionPlan,
        initial_policy_result: PolicyResult | None = None,
        initial_tool_evidence: Dict[str, Any] | None = None,
        initial_runtime_context: Dict[str, Any] | None = None,
        conversation_state: ConversationState | None = None,
        execution_mode: str = ToolExecutionMode.SHADOW,
    ) -> RuntimeExecutorResult:
        current = state
        outcomes: List[Dict[str, Any]] = []
        policy_result: PolicyResult | None = initial_policy_result
        tool_evidence: Dict[str, Any] = dict(initial_tool_evidence or {})
        runtime_context: Dict[str, Any] = dict(initial_runtime_context or {})
        interrupted = False
        selected_program: str | None = None

        if policy_result is None and not plan_has_step(execution_plan, "policy"):
            policy_execution = self.handlers.resolve("policy").execute(
                StepExecutionContext(
                    state=current,
                    event=event,
                    execution_plan=execution_plan,
                    step=step_from_plan(execution_plan, "policy"),
                    services=self.services,
                    conversation_state=conversation_state,
                    domain_context=self.domain_context,
                    runtime_config=_runtime_config(execution_mode),
                )
            )
            policy_result = policy_execution.policy_result
            if policy_execution.state is not None:
                current = policy_execution.state

        for step in execution_plan.steps:
            if interrupted and step.name not in {"handoff", "escalation", "memory", "context", "output"}:
                continue

            handler = self.handlers.resolve(step.name)
            result = handler.execute(
                StepExecutionContext(
                    state=current,
                    event=event,
                    execution_plan=execution_plan,
                    step=step,
                    services=self.services,
                    conversation_state=conversation_state,
                    domain_context=self.domain_context,
                    policy_result=policy_result,
                    tool_evidence=tool_evidence,
                    runtime_context=runtime_context,
                    runtime_config=_runtime_config(execution_mode),
                )
            )
            outcomes.append(result.outcome)

            if result.policy_result is not None:
                policy_result = result.policy_result
                runtime_context["policy_result"] = policy_result.to_dict()
            if result.produced_evidence:
                tool_evidence = result.produced_evidence
                runtime_context["tool_evidence"] = tool_evidence
            if result.state is not None:
                current = result.state
            if result.data.get("selected_program"):
                selected_program = str(result.data["selected_program"])
            if result.data.get("relevant_memory") is not None:
                runtime_context["relevant_memory"] = result.data["relevant_memory"]

            if result.status == "interrupted" or result.continue_execution is False:
                interrupted = True

        policy_data = policy_result.to_dict() if policy_result else {}
        return RuntimeExecutorResult(
            outcomes=outcomes,
            final_state=current,
            execution_plan=execution_plan.to_dict(),
            policy_result=policy_data,
            tool_evidence=tool_evidence,
            selected_program=selected_program or current.selected_program,
            response=current.response,
            interrupted=interrupted,
        )

    def execute_step_slice(
        self,
        *,
        event: Event,
        state: CognitiveState,
        execution_plan: ExecutionPlan,
        step_names: List[str],
        initial_policy_result: PolicyResult | None = None,
        initial_tool_evidence: Dict[str, Any] | None = None,
        initial_runtime_context: Dict[str, Any] | None = None,
        conversation_state: ConversationState | None = None,
        execution_mode: str = ToolExecutionMode.SHADOW,
    ) -> RuntimeExecutorResult:
        selected_steps = set(step_names)
        current = state
        outcomes: List[Dict[str, Any]] = []
        policy_result = initial_policy_result
        tool_evidence: Dict[str, Any] = dict(initial_tool_evidence or {})
        runtime_context: Dict[str, Any] = dict(initial_runtime_context or {})

        for step in execution_plan.steps:
            if step.name not in selected_steps:
                continue

            result = self.handlers.resolve(step.name).execute(
                StepExecutionContext(
                    state=current,
                    event=event,
                    execution_plan=execution_plan,
                    step=step,
                    services=self.services,
                    conversation_state=conversation_state,
                    domain_context=self.domain_context,
                    policy_result=policy_result,
                    tool_evidence=tool_evidence,
                    runtime_context=runtime_context,
                    runtime_config=_runtime_config(execution_mode),
                )
            )
            outcomes.append(result.outcome)
            if result.policy_result is not None:
                policy_result = result.policy_result
            if result.produced_evidence:
                tool_evidence = result.produced_evidence
            if result.state is not None:
                current = result.state
            if result.data.get("relevant_memory") is not None:
                runtime_context["relevant_memory"] = result.data["relevant_memory"]

        return RuntimeExecutorResult(
            mode=f"{execution_mode}_step_slice",
            outcomes=outcomes,
            final_state=current,
            execution_plan=execution_plan.to_dict(),
            policy_result=policy_result.to_dict() if policy_result else {},
            tool_evidence=tool_evidence,
            selected_program=current.selected_program,
            response=current.response,
        )


def compare_runtime_executions(
    *,
    official_state: CognitiveState,
    shadow_result: RuntimeExecutorResult,
    official_engine: str = "official_runtime",
    shadow_engine: str | None = None,
) -> RuntimeExecutorComparison:
    official_outcomes = list(official_state.facts.get("execution_step_outcomes", []))
    shadow = shadow_result.to_dict()
    official = {
        "outcomes": official_outcomes,
        "execution_plan": dict(official_state.facts.get("zero_cost_execution_plan") or {}),
        "step_order": _step_order(official_outcomes),
        "executors": _executors(official_outcomes),
        "statuses": _statuses(official_outcomes),
        "tool_evidence": dict(official_state.tool_evidence),
        "selected_program": official_state.selected_program,
        "response": official_state.response,
        "policy_result": dict(official_state.policy_result or {}),
        "final_state": _state_summary(official_state),
        "engine": official_engine,
    }
    shadow_summary = {
        "outcomes": shadow["outcomes"],
        "execution_plan": dict(shadow["execution_plan"]),
        "step_order": _step_order(shadow["outcomes"]),
        "executors": _executors(shadow["outcomes"]),
        "statuses": _statuses(shadow["outcomes"]),
        "tool_evidence": dict(shadow_result.tool_evidence),
        "selected_program": shadow_result.selected_program,
        "response": shadow_result.response,
        "policy_result": dict(shadow_result.policy_result),
        "final_state": _state_summary(shadow_result.final_state),
        "engine": shadow_engine or shadow["mode"],
    }

    divergences: List[Dict[str, Any]] = []
    _compare_value(divergences, "execution_plan", official["execution_plan"], shadow_summary["execution_plan"])
    _compare_value(divergences, "step_order", official["step_order"], shadow_summary["step_order"])
    _compare_value(divergences, "handlers", official["executors"], shadow_summary["executors"])
    _compare_value(divergences, "statuses", official["statuses"], shadow_summary["statuses"])
    _compare_value(divergences, "interruptions", _interruptions(official_outcomes), _interruptions(shadow["outcomes"]))
    _compare_value(divergences, "evidence", official["tool_evidence"], shadow_summary["tool_evidence"])
    _compare_value(divergences, "selected_program", official["selected_program"], shadow_summary["selected_program"])
    _compare_value(divergences, "response", official["response"], shadow_summary["response"])
    _compare_value(
        divergences,
        "policy_decision",
        official["policy_result"].get("decision"),
        shadow_summary["policy_result"].get("decision"),
    )
    _compare_value(divergences, "outcomes", _outcome_core(official_outcomes), _outcome_core(shadow["outcomes"]))
    _compare_value(divergences, "final_state", official["final_state"], shadow_summary["final_state"])

    total_checks = 11
    score = round((total_checks - len(divergences)) / total_checks, 4)
    return RuntimeExecutorComparison(
        equivalent=not divergences,
        equivalence_score=score,
        official=official,
        shadow=shadow_summary,
        divergences=divergences,
    )


def _compare_value(divergences: List[Dict[str, Any]], field: str, official: Any, shadow: Any) -> None:
    if official == shadow:
        return
    divergences.append(
        {
            "field": field,
            "classification": "architectural_difference",
            "official": official,
            "shadow": shadow,
            "probable_reason": _probable_reason(field),
        }
    )


def _probable_reason(field: str) -> str:
    reasons = {
        "outcomes": "Outcome data differs after removing timing fields.",
        "evidence": "Tool execution evidence differs between official and shadow execution.",
        "response": "Final response differs between official and shadow execution.",
        "selected_program": "Kernel program selection differs.",
        "final_state": "Observable final cognitive state differs after removing timeline and version noise.",
        "execution_plan": "Execution plan differs between official and comparison execution.",
    }
    return reasons.get(field, "Official runtime and shadow executor produced different projections.")


def _state_summary(state: CognitiveState | None) -> Dict[str, Any]:
    if state is None:
        return {}
    return {
        "response": state.response,
        "selected_program": state.selected_program,
        "policy_decision": (state.policy_result or {}).get("decision"),
        "tool_evidence": dict(state.tool_evidence),
        "active_mission": dict(state.active_mission or {}),
        "context_bundle": _context_summary(state.context_bundle),
        "memory_snapshot": dict(state.memory_snapshot or {}),
    }


def _context_summary(context_bundle: Dict[str, Any] | None) -> Dict[str, Any]:
    if not context_bundle:
        return {}
    summary = dict(context_bundle)
    summary.pop("facts", None)
    return summary


def _step_order(outcomes: List[Dict[str, Any]]) -> List[str]:
    return [str(outcome.get("step")) for outcome in outcomes]


def _executors(outcomes: List[Dict[str, Any]]) -> List[str]:
    return [str(outcome.get("executor")) for outcome in outcomes]


def _statuses(outcomes: List[Dict[str, Any]]) -> List[str]:
    return [str(outcome.get("status")) for outcome in outcomes]


def _interruptions(outcomes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(outcome.get("interruption") or {}) for outcome in outcomes if outcome.get("interruption")]


def _outcome_core(outcomes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    core = []
    for outcome in outcomes:
        core.append(
            {
                "step": outcome.get("step"),
                "executor": outcome.get("executor"),
                "status": outcome.get("status"),
                "evidence": outcome.get("evidence") or {},
                "error": outcome.get("error"),
                "interruption": outcome.get("interruption") or {},
                "result": _result_core(outcome.get("result") or {}),
            }
        )
    return core


def _runtime_config(execution_mode: str) -> Dict[str, Any]:
    runtime_engine = "runtime_executor" if execution_mode == ToolExecutionMode.OFFICIAL else "runtime_executor_shadow"
    return {
        "origin": "runtime_executor",
        "runtime_engine": runtime_engine,
        "tool_execution_mode": execution_mode,
    }


def _result_core(result: Dict[str, Any]) -> Dict[str, Any]:
    core = dict(result)
    core.pop("tool_execution", None)
    return core
