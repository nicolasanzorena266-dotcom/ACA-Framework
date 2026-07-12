from __future__ import annotations

from typing import Any, Callable, Dict

from aca_kernel.core.state import CognitiveState
from aca_os.policy_manager import PolicyDecision, PolicyResult
from zero_cost.execution_plan import ExecutionPlan


def build_execution_authority(
    *,
    execution_plan: ExecutionPlan,
    selected_program: str | None,
    executor: str,
    policy_result: PolicyResult,
) -> Dict[str, Any]:
    plan = execution_plan.to_dict()
    planned_program = str(plan.get("kernel_program") or "")
    status = "executed_as_planned" if selected_program == planned_program else "controlled_fallback"
    modification: Dict[str, Any] | None = None

    if policy_result.decision == PolicyDecision.ESCALATE:
        status = "policy_interrupted"
        modification = {
            "component": "policy_manager",
            "reason": policy_result.reason,
            "triggered_rules": list(policy_result.triggered_rules),
            "modifications": list(policy_result.modifications),
        }
    elif policy_result.modifications:
        status = "policy_modified"
        modification = {
            "component": "policy_manager",
            "reason": policy_result.reason,
            "triggered_rules": list(policy_result.triggered_rules),
            "modifications": list(policy_result.modifications),
        }
    elif selected_program != planned_program:
        modification = {
            "component": "graph_compiler",
            "reason": "planned_kernel_program_unavailable",
            "planned_program": planned_program,
            "selected_program": selected_program,
        }

    return {
        "contract": "runtime_execution_authority.v1",
        "source": "zero_cost_execution_plan",
        "flow": plan.get("flow"),
        "source_action": plan.get("source_action"),
        "planned_kernel_program": planned_program,
        "selected_program": selected_program,
        "executor": executor,
        "status": status,
        "policy_decision": policy_result.decision,
        "policy_evaluation": {
            "source": policy_result.source,
            "reason": policy_result.reason,
            "validations": list(policy_result.validations),
            "triggered_rules": list(policy_result.triggered_rules),
        },
        "modification": modification,
    }


def record_execution_authority(
    state: CognitiveState,
    *,
    execution_plan: ExecutionPlan,
    selected_program: str | None,
    executor: str,
    policy_result: PolicyResult,
    emit: Callable[..., None] | None = None,
) -> CognitiveState:
    authority = build_execution_authority(
        execution_plan=execution_plan,
        selected_program=selected_program,
        executor=executor,
        policy_result=policy_result,
    )
    facts = dict(state.facts)
    facts["runtime_execution_authority"] = authority
    updated = state.evolve("EXECUTION_AUTHORITY", facts=facts)
    if emit:
        emit("runtime.execution_authority_resolved", execution_authority=authority)
    return updated
