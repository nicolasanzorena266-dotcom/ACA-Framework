from aca_kernel.core.events import Event
from aca_os.conversation_state import conversation_plan_contract
from sdk.factory import build_galicia_runtime


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _conversation(runtime, conversation_id: str):
    return runtime.conversation_manager.conversation_state(conversation_id)


def _plan(state):
    return state.facts["conversation_plan"]["plan"]


def _step_ids(steps):
    return [step["id"] for step in steps]


def test_conversation_plan_contract_is_explicit_and_dynamic():
    contract = conversation_plan_contract()

    assert contract["contract"] == "conversation_plan.v1"
    assert contract["required_fields"] == [
        "active_plan",
        "completed_steps",
        "pending_steps",
        "abandoned_steps",
        "replanning_reason",
        "inserted_steps",
        "skipped_steps",
        "conversation_progress",
    ]
    assert contract["persistent_projection"] == "conversation_plan"


def test_new_evidence_completes_and_skips_unnecessary_steps_without_reasking():
    runtime = build_galicia_runtime()
    _run(runtime, "dyn-loaded", "Me chocaron ayer")
    _run(runtime, "dyn-loaded", "No hubo lesionados y soy asegurado.")

    state = _run(runtime, "dyn-loaded", "Ya cargue todo.")
    plan = _plan(state)

    assert plan["replanning_reason"] == "new_evidence_completed_or_skipped_steps"
    assert {"confirm_claim_report_loaded", "confirm_documentation_available"}.issubset(_step_ids(plan["completed_steps"]))
    assert {"confirm_claim_report_loaded", "confirm_documentation_available"}.issubset(_step_ids(plan["skipped_steps"]))
    assert plan["pending_steps"] == []
    assert plan["conversation_progress"]["ratio"] == 1.0
    assert "La denuncia ya esta cargada?" not in state.response
    assert "Tenes toda la documentacion?" not in state.response


def test_lateral_question_is_inserted_and_main_plan_is_preserved():
    runtime = build_galicia_runtime()
    _run(runtime, "dyn-lateral", "Me chocaron ayer")
    _run(runtime, "dyn-lateral", "No hubo lesionados.")

    state = _run(runtime, "dyn-lateral", "Y cuanto tarda normalmente?")
    plan = _plan(state)
    conversation = _conversation(runtime, "dyn-lateral")

    assert plan["replanning_reason"] == "side_step_inserted_preserve_active_plan"
    assert _step_ids(plan["inserted_steps"]) == ["answer_lateral_process_timing"]
    assert "confirm_user_role" in _step_ids(plan["pending_steps"])
    assert conversation.active_mission["next_act"] == "ask_user_role"
    assert "Sobre cuando te van a contactar" in state.response
    assert "Respecto a tu denuncia" in state.response
    assert "sos asegurado de Galicia o tercero damnificado?" in state.response


def test_unexpected_out_of_order_information_reorders_without_resetting_goal():
    runtime = build_galicia_runtime()
    _run(runtime, "dyn-out-of-order", "Me chocaron ayer")

    state = _run(runtime, "dyn-out-of-order", "Soy tercero damnificado.")
    plan = _plan(state)
    conversation = _conversation(runtime, "dyn-out-of-order")

    assert "confirm_user_role" in _step_ids(plan["completed_steps"])
    assert "confirm_injuries" in _step_ids(plan["pending_steps"])
    assert plan["active_plan"]["current_step"]["id"] == "confirm_injuries"
    assert conversation.active_mission["next_act"] == "ask_injuries"
    assert "Recordas si alguna persona resulto herida" in state.response


def test_two_answers_in_one_turn_complete_multiple_steps():
    runtime = build_galicia_runtime()
    _run(runtime, "dyn-multiple", "Me chocaron ayer")

    state = _run(runtime, "dyn-multiple", "No hubo lesionados y soy asegurado.")
    plan = _plan(state)

    assert {"confirm_injuries", "confirm_user_role"}.issubset(_step_ids(plan["completed_steps"]))
    assert plan["active_plan"]["current_step"]["id"] == "confirm_claim_report_loaded"
    assert "confirm_claim_report_loaded" in _step_ids(plan["pending_steps"])
    assert "denuncia ya esta cargada" in state.response


def test_conversation_plan_is_available_in_runtime_introspection_record():
    runtime = build_galicia_runtime()

    state = _run(runtime, "dyn-observable", "Me chocaron ayer")
    runtime_record = state.facts["conversation_state_runtime"]

    assert state.facts["conversation_plan"]["plan"]["contract"] == "conversation_plan.v1"
    assert runtime_record["conversation_plan"]["plan"]["active_plan"]["mission_type"] == "auto_claim_guidance"
    assert any(
        projection["reason"] == "dynamic_conversation_planning"
        for projection in runtime_record["projections"]
    )
