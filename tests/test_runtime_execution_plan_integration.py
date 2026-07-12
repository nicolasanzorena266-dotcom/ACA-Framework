from aca_kernel.core.events import Event
from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime
from sdk.factory import build_galicia_runtime


def test_runtime_persists_zero_cost_execution_plan():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="Que es CLEAS?"))

    plan = state.facts["zero_cost_execution_plan"]
    assert plan["flow"] == "knowledge_lookup"
    assert plan["kernel_program"] == "knowledge_lookup"
    assert [step["name"] for step in plan["steps"]] == [
        "policy",
        "tool_lookup",
        "kernel",
        "memory",
        "context",
        "output",
    ]
    assert plan["steps"][1]["payload"] == {"tool_key": "cleas"}


def test_runtime_timeline_includes_execution_plan_operation():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="quiero hablar con un asesor"))

    operations = [entry["operation"] for entry in state.timeline]
    assert "INTENT_MATCH" in operations
    assert "ACTION_PLAN" in operations
    assert "FLOW_ROUTE" in operations
    assert "EXECUTION_PLAN" in operations


def test_runtime_execution_plan_authorizes_kernel_program():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="Me chocaron ayer"))

    plan = state.facts["zero_cost_execution_plan"]
    authority = state.facts["runtime_execution_authority"]
    assert plan["flow"] == "guided_process"
    assert plan["kernel_program"] == "auto_claim_guidance"
    assert authority["planned_kernel_program"] == "auto_claim_guidance"
    assert authority["selected_program"] == "auto_claim_guidance"
    assert authority["status"] == "executed_as_planned"
    assert authority["policy_evaluation"]["source"] == "execution_plan_policy"
    assert authority["policy_evaluation"]["reason"] == "execution_plan_authorized"
    assert state.selected_program == "auto_claim_guidance"


def test_runtime_records_policy_interruption_of_execution_plan():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="quiero hablar con un asesor"))

    authority = state.facts["runtime_execution_authority"]
    assert state.facts["zero_cost_execution_plan"]["flow"] == "human_handoff"
    assert authority["status"] == "policy_interrupted"
    assert authority["executor"] == "runtime_executor"
    assert authority["policy_evaluation"]["source"] == "execution_plan_policy"
    assert authority["modification"]["component"] == "policy_manager"
    assert "human_requested" in authority["modification"]["triggered_rules"]


def test_runtime_policy_validates_knowledge_lookup_plan_without_text_reclassification():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="Que es CLEAS?"))

    policy = state.policy_result
    authority = state.facts["runtime_execution_authority"]
    assert policy["decision"] == "USE_TOOL"
    assert policy["reason"] == "execution_plan_tool_lookup_authorized"
    assert policy["source"] == "execution_plan_policy"
    assert any(validation["name"] == "tool_key_present" for validation in policy["validations"])
    assert authority["policy_evaluation"]["reason"] == "execution_plan_tool_lookup_authorized"


def test_runtime_records_execution_step_outcomes_in_plan_order():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="Que es CLEAS?"))

    outcomes = state.facts["execution_step_outcomes"]
    assert [outcome["step"] for outcome in outcomes] == [
        "policy",
        "tool_lookup",
        "kernel",
        "memory",
        "context",
        "output",
    ]
    assert all(outcome["started_at"] for outcome in outcomes)
    assert all(outcome["finished_at"] for outcome in outcomes)
    assert all(outcome["duration_ms"] >= 0 for outcome in outcomes)
    assert outcomes[0]["executor"] == "policy_manager"
    assert outcomes[1]["evidence"]["cleas"]["name"] == "CLEAS"
    assert outcomes[2]["result"]["selected_program"] == "knowledge_lookup"
    assert outcomes[-1]["result"]["response"]


def test_runtime_records_interrupted_step_outcomes():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="Necesito hablar con un asesor"))

    outcomes = state.facts["execution_step_outcomes"]
    assert [outcome["step"] for outcome in outcomes] == [
        "policy",
        "handoff",
        "memory",
        "context",
        "output",
    ]
    assert outcomes[0]["status"] == "interrupted"
    assert outcomes[0]["interruption"]["reason"] == "user_requested_human"
    assert outcomes[1]["executor"] == "policy_manager"
    assert outcomes[1]["state_changes"]["operation"] == "POLICY_ESCALATE"
    assert not any(outcome["step"] == "kernel" for outcome in outcomes)


def test_runtime_records_controlled_tool_error_outcome():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
        domain_context={},
    )

    state = runtime.process(Event(type="user_message", payload="Que es CLEAS?"))

    tool_outcome = next(outcome for outcome in state.facts["execution_step_outcomes"] if outcome["step"] == "tool_lookup")
    assert tool_outcome["status"] == "error"
    assert tool_outcome["error"] == "Tool not registered: knowledge_base"
    assert tool_outcome["evidence"] == {"tool_error": "Tool not registered: knowledge_base"}


def test_runtime_records_skipped_tool_step_when_policy_restricts_plan():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
        domain_context={"concepts": {"franquicia": {}}},
    )

    state = runtime.process(Event(type="user_message", payload="Que es CLEAS?"))

    tool_outcome = next(outcome for outcome in state.facts["execution_step_outcomes"] if outcome["step"] == "tool_lookup")
    assert tool_outcome["status"] == "skipped"
    assert tool_outcome["result"]["tool_key"] == "cleas"
    assert state.policy_result["reason"] == "planned_tool_unavailable"
