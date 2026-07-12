import pytest

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.core.state import CognitiveState
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.context_manager import ContextManager
from aca_os.memory_engine import MemoryEngine
from aca_os.mission_manager import MissionManager
from aca_os.policy_manager import PolicyManager
from aca_os.runtime import ACAOSRuntime
from aca_os.runtime_executor import RuntimeExecutor, RuntimeExecutorResult, compare_runtime_executions
from aca_os.step_handlers import StepRuntimeServices, build_default_step_handler_registry
from aca_os.tool_engine import ToolEngine
from sdk.factory import build_galicia_runtime
from zero_cost.action_planner import ActionPlanner
from zero_cost.execution_plan import ExecutionPlan
from zero_cost.intent_matcher import IntentMatch


def _shadow_for(message: str):
    runtime = build_galicia_runtime()
    state = runtime.process(Event(type="user_message", payload=message))
    return runtime, state, state.facts["runtime_executor_shadow"]


def _services() -> StepRuntimeServices:
    return StepRuntimeServices(
        policy_manager=PolicyManager(),
        tool_engine=ToolEngine(),
        compiler=GraphCompiler(),
        kernel=ACAKernel(build_default_registry()),
        mission_manager=MissionManager(),
        memory_engine=MemoryEngine(),
        context_manager=ContextManager(),
    )


class _WeakIntentMatcher:
    def match(self, text: object) -> IntentMatch:
        return IntentMatch(intent="weak_intent", confidence=0.3, matched_terms=["ambiguous"])


def _clarification_runtime() -> ACAOSRuntime:
    return ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
        intent_matcher=_WeakIntentMatcher(),
        action_planner=ActionPlanner(
            {
                "weak_intent": {
                    "action": "process_guidance",
                    "min_confidence": 0.8,
                }
            }
        ),
        domain_context={},
    )


@pytest.mark.parametrize(
    ("message", "expected_steps"),
    [
        ("Que es CLEAS?", ["policy", "tool_lookup", "kernel", "memory", "context", "output"]),
        ("Me chocaron ayer", ["policy", "kernel", "memory", "context", "output"]),
        ("asdf qwer zxcv", ["kernel", "memory", "context", "output"]),
        ("quiero hablar con un asesor", ["policy", "handoff", "memory", "context", "output"]),
        ("Cuando me pagan?", ["policy", "escalation", "memory", "context", "output"]),
    ],
)
def test_runtime_executor_shadow_matches_official_execution(message, expected_steps):
    _, _, shadow = _shadow_for(message)

    assert shadow["contract"] == "runtime_executor_shadow_comparison.v1"
    assert shadow["equivalent"] is True
    assert shadow["equivalence_score"] == 1.0
    assert shadow["divergences"] == []
    assert shadow["official"]["step_order"] == expected_steps
    assert shadow["shadow"]["step_order"] == expected_steps
    assert shadow["official"]["executors"] == shadow["shadow"]["executors"]
    assert shadow["official"]["statuses"] == shadow["shadow"]["statuses"]
    assert shadow["official"]["final_state"] == shadow["shadow"]["final_state"]


def test_runtime_executor_shadow_matches_tool_lookup_evidence_and_response():
    _, state, shadow = _shadow_for("Que es CLEAS?")

    assert state.facts["runtime_execution_engine"]["official_engine"] == "runtime_executor"
    assert shadow["official"]["tool_evidence"] == shadow["shadow"]["tool_evidence"]
    assert shadow["shadow"]["tool_evidence"]["cleas"]["name"] == "CLEAS"
    assert shadow["official"]["response"] == shadow["shadow"]["response"] == state.response
    assert shadow["official"]["selected_program"] == shadow["shadow"]["selected_program"] == "knowledge_lookup"


def test_runtime_executor_officially_executes_fallback_slice():
    _, state, comparison = _shadow_for("asdf qwer zxcv")

    engine = state.facts["runtime_execution_engine"]
    authority = state.facts["runtime_execution_authority"]

    assert engine["official_engine"] == "runtime_executor"
    assert engine["validation_engine"] == "legacy_runtime_validation"
    assert engine["selection_reason"] == "migrated_flow_slice_1"
    assert engine["flow"] == "fallback"
    assert authority["executor"] == "runtime_executor"
    assert comparison["official"]["engine"] == "runtime_executor"
    assert comparison["shadow"]["engine"] == "legacy_runtime_validation"
    assert comparison["equivalent"] is True
    assert comparison["official"]["step_order"] == ["kernel", "memory", "context", "output"]
    assert state.selected_program == "fallback"


def test_runtime_executor_officially_executes_static_response_slice():
    _, state, comparison = _shadow_for("hola")

    engine = state.facts["runtime_execution_engine"]
    authority = state.facts["runtime_execution_authority"]

    assert state.facts["zero_cost_execution_plan"]["flow"] == "static_response"
    assert engine["official_engine"] == "runtime_executor"
    assert engine["selection_reason"] == "migrated_flow_slice_1"
    assert authority["planned_kernel_program"] == "greeting"
    assert authority["executor"] == "runtime_executor"
    assert comparison["shadow"]["engine"] == "legacy_runtime_validation"
    assert comparison["equivalent"] is True
    assert comparison["official"]["response"] == comparison["shadow"]["response"] == state.response
    assert state.selected_program == "greeting"


def test_runtime_executor_officially_executes_guided_process_slice():
    _, state, comparison = _shadow_for("Me chocaron ayer y el tercero no hizo la denuncia")

    engine = state.facts["runtime_execution_engine"]
    authority = state.facts["runtime_execution_authority"]
    outcomes = state.facts["execution_step_outcomes"]

    assert state.facts["zero_cost_execution_plan"]["flow"] == "guided_process"
    assert engine["official_engine"] == "runtime_executor"
    assert engine["validation_engine"] == "legacy_runtime_validation"
    assert engine["selection_reason"] == "migrated_flow_slice_2"
    assert engine["comparison"]["equivalence_percentage"] == 100.0
    assert engine["comparison"]["divergences"] == []
    assert authority["planned_kernel_program"] == "auto_claim_guidance"
    assert authority["executor"] == "runtime_executor"
    assert comparison["official"]["engine"] == "runtime_executor"
    assert comparison["shadow"]["engine"] == "legacy_runtime_validation"
    assert comparison["official"]["execution_plan"] == comparison["shadow"]["execution_plan"]
    assert comparison["equivalent"] is True
    assert [outcome["step"] for outcome in outcomes] == ["policy", "kernel", "memory", "context", "output"]
    assert [outcome["status"] for outcome in outcomes] == ["success", "success", "success", "success", "success"]
    assert state.selected_program == "auto_claim_guidance"
    assert state.entities["event"] == "vehicle_collision"
    assert state.facts["event_type"] == "vehicle_collision"
    assert state.hypotheses["needs_claim_guidance"] == 0.92
    assert "ask_if_injuries" in state.plan
    assert "current_mission_type" in state.memory_snapshot["relevant"]
    assert state.context_bundle["mission"]["type"] == "auto_claim_guidance"
    assert state.response == comparison["shadow"]["response"]


def test_runtime_executor_officially_executes_knowledge_lookup_slice():
    _, state, comparison = _shadow_for("Que es CLEAS?")

    engine = state.facts["runtime_execution_engine"]
    authority = state.facts["runtime_execution_authority"]
    outcomes = state.facts["execution_step_outcomes"]
    official_tool = next(outcome for outcome in outcomes if outcome["step"] == "tool_lookup")
    legacy_tool = next(outcome for outcome in comparison["shadow"]["outcomes"] if outcome["step"] == "tool_lookup")

    assert engine["official_engine"] == "runtime_executor"
    assert engine["validation_engine"] == "legacy_runtime_validation"
    assert engine["selection_reason"] == "migrated_flow_slice_3"
    assert engine["flow"] == "knowledge_lookup"
    assert engine["tool_executions"][0]["action"] == "execute"
    assert engine["tool_executions"][0]["executed"] is True
    assert authority["executor"] == "runtime_executor"
    assert comparison["official"]["engine"] == "runtime_executor"
    assert comparison["shadow"]["engine"] == "legacy_runtime_validation"
    assert comparison["equivalent"] is True
    assert [outcome["step"] for outcome in outcomes] == ["policy", "tool_lookup", "kernel", "memory", "context", "output"]
    assert official_tool["result"]["tool_execution"]["mode"] == "official"
    assert official_tool["result"]["tool_execution"]["action"] == "execute"
    assert official_tool["result"]["tool_execution"]["executed"] is True
    assert legacy_tool["result"]["tool_execution"]["action"] == "reuse_existing_evidence"
    assert legacy_tool["result"]["tool_execution"]["executed"] is False
    assert state.tool_evidence["cleas"]["name"] == "CLEAS"
    assert state.context_bundle["tool_evidence"]["cleas"]["name"] == "CLEAS"
    assert state.memory_snapshot["consolidated"]["last_mission_type"] == "knowledge_lookup"
    assert state.response == comparison["shadow"]["response"]


def test_non_migrated_clarification_flow_still_uses_legacy_runtime_with_shadow_comparison():
    runtime = _clarification_runtime()
    state = runtime.process(Event(type="user_message", payload="ambiguous"))
    comparison = state.facts["runtime_executor_shadow"]

    engine = state.facts["runtime_execution_engine"]

    assert engine["official_engine"] == "legacy_runtime"
    assert engine["validation_engine"] == "runtime_executor_shadow"
    assert engine["selection_reason"] == "flow_not_migrated"
    assert engine["flow"] == "clarification"
    assert comparison["official"]["engine"] == "legacy_runtime"
    assert comparison["shadow"]["engine"] == "runtime_executor_shadow"
    assert comparison["equivalent"] is True


def test_runtime_exposes_legacy_runtime_executor_as_isolated_engine():
    runtime = _clarification_runtime()
    state = runtime.process(Event(type="user_message", payload="ambiguous"))

    engine = state.facts["runtime_execution_engine"]

    assert runtime.legacy_runtime.__class__.__name__ == "LegacyRuntimeExecutor"
    assert engine["official_engine"] == "legacy_runtime"
    assert state.facts["runtime_execution_authority"]["executor"] == "kernel"


def test_runtime_executor_flows_use_legacy_only_as_validation_engine():
    _, state, comparison = _shadow_for("Que es CLEAS?")

    engine = state.facts["runtime_execution_engine"]

    assert engine["official_engine"] == "runtime_executor"
    assert engine["validation_engine"] == "legacy_runtime_validation"
    assert comparison["official"]["engine"] == "runtime_executor"
    assert comparison["shadow"]["engine"] == "legacy_runtime_validation"


def test_runtime_executor_officially_executes_human_handoff_slice():
    _, state, comparison = _shadow_for("quiero hablar con un asesor")

    engine = state.facts["runtime_execution_engine"]
    authority = state.facts["runtime_execution_authority"]
    outcomes = state.facts["execution_step_outcomes"]

    assert state.facts["zero_cost_execution_plan"]["flow"] == "human_handoff"
    assert engine["official_engine"] == "runtime_executor"
    assert engine["validation_engine"] == "legacy_runtime_validation"
    assert engine["selection_reason"] == "migrated_flow_slice_4"
    assert engine["interruption"]["present"] is True
    assert engine["interruption"]["type"] == "human_handoff"
    assert engine["interruption"]["step"] == "handoff"
    assert engine["interruption"]["origin_component"] == "policy_manager"
    assert engine["interruption"]["executed_by"] == "runtime_executor"
    assert engine["interruption"]["reason"] == "user_requested_human"
    assert authority["executor"] == "runtime_executor"
    assert authority["status"] == "policy_interrupted"
    assert authority["modification"]["component"] == "policy_manager"
    assert comparison["official"]["engine"] == "runtime_executor"
    assert comparison["shadow"]["engine"] == "legacy_runtime_validation"
    assert comparison["equivalent"] is True
    assert [outcome["step"] for outcome in outcomes] == ["policy", "handoff", "memory", "context", "output"]
    assert [outcome["status"] for outcome in outcomes] == ["interrupted", "success", "success", "success", "success"]
    assert outcomes[0]["interruption"] == comparison["shadow"]["outcomes"][0]["interruption"]
    assert outcomes[1]["state_changes"]["operation"] == "POLICY_ESCALATE"
    assert state.selected_program is None


def test_runtime_executor_officially_executes_safe_escalation_slice():
    _, state, comparison = _shadow_for("Cuando me pagan?")

    engine = state.facts["runtime_execution_engine"]
    authority = state.facts["runtime_execution_authority"]
    outcomes = state.facts["execution_step_outcomes"]

    assert state.facts["zero_cost_execution_plan"]["flow"] == "safe_escalation"
    assert engine["official_engine"] == "runtime_executor"
    assert engine["validation_engine"] == "legacy_runtime_validation"
    assert engine["selection_reason"] == "migrated_flow_slice_4"
    assert engine["interruption"]["present"] is True
    assert engine["interruption"]["type"] == "safe_escalation"
    assert engine["interruption"]["step"] == "escalation"
    assert engine["interruption"]["origin_component"] == "policy_manager"
    assert engine["interruption"]["executed_by"] == "runtime_executor"
    assert engine["interruption"]["reason"] == "request_requires_real_file_or_crm_access"
    assert authority["executor"] == "runtime_executor"
    assert authority["status"] == "policy_interrupted"
    assert "no_real_claim_status" in authority["modification"]["triggered_rules"]
    assert comparison["official"]["engine"] == "runtime_executor"
    assert comparison["shadow"]["engine"] == "legacy_runtime_validation"
    assert comparison["equivalent"] is True
    assert [outcome["step"] for outcome in outcomes] == ["policy", "escalation", "memory", "context", "output"]
    assert [outcome["status"] for outcome in outcomes] == ["interrupted", "success", "success", "success", "success"]
    assert outcomes[0]["interruption"] == comparison["shadow"]["outcomes"][0]["interruption"]
    assert outcomes[1]["state_changes"]["operation"] == "POLICY_ESCALATE"
    assert state.selected_program is None


def test_runtime_executor_shadow_matches_policy_interruption():
    _, state, shadow = _shadow_for("quiero hablar con un asesor")

    assert state.facts["runtime_execution_authority"]["status"] == "policy_interrupted"
    assert shadow["official"]["statuses"][0] == "interrupted"
    assert shadow["shadow"]["statuses"][0] == "interrupted"
    assert shadow["official"]["outcomes"][0]["interruption"] == shadow["shadow"]["outcomes"][0]["interruption"]
    assert not any(outcome["step"] == "kernel" for outcome in shadow["shadow"]["outcomes"])


def test_runtime_executor_shadow_is_visible_through_introspection():
    runtime, _, shadow = _shadow_for("Me chocaron ayer")

    snapshot = runtime.inspect_runtime().to_dict()

    assert snapshot["last_state"]["runtime_execution_engine"]["official_engine"] == "runtime_executor"
    assert snapshot["last_state"]["runtime_execution_engine"]["flow"] == "guided_process"
    assert snapshot["last_state"]["runtime_executor_shadow"]["contract"] == shadow["contract"]
    assert snapshot["last_state"]["runtime_executor_shadow"]["equivalent"] is True


def test_runtime_executor_comparison_records_controlled_divergence():
    _, state, _ = _shadow_for("Que es CLEAS?")
    divergent = RuntimeExecutorResult(
        outcomes=state.facts["execution_step_outcomes"],
        final_state=state,
        execution_plan=state.facts["zero_cost_execution_plan"],
        policy_result=state.policy_result or {},
        tool_evidence=state.tool_evidence,
        selected_program=state.selected_program,
        response="respuesta divergente",
    )

    comparison = compare_runtime_executions(official_state=state, shadow_result=divergent)

    assert comparison.equivalent is False
    assert comparison.equivalence_score < 1.0
    assert any(divergence["field"] == "response" for divergence in comparison.divergences)


def test_runtime_executor_fails_explicitly_for_missing_handler():
    plan = ExecutionPlan.from_flow(
        {
            "flow": "fallback",
            "source_action": "fallback_response",
            "steps": ["policy", "unknown_step"],
        }
    )
    executor = RuntimeExecutor(
        handlers=build_default_step_handler_registry(),
        services=_services(),
        domain_context={},
    )

    with pytest.raises(KeyError):
        executor.execute(
            event=Event(type="user_message", payload="hola"),
            state=CognitiveState(facts={"zero_cost_execution_plan": plan.to_dict()}),
            execution_plan=plan,
        )
