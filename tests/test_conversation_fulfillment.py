from aca_kernel.core.events import Event
from aca_os.conversation_state import conversation_fulfillment_contract
from sdk.factory import build_galicia_runtime


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _fulfillment(state):
    return state.facts["conversation_fulfillment"]["fulfillment"]


def _step_ids(steps):
    return [step["id"] for step in steps]


def _actions(fulfillment):
    return [action["action"] for action in fulfillment["recovery_actions"]]


def test_conversation_fulfillment_contract_is_explicit():
    contract = conversation_fulfillment_contract()

    assert contract["contract"] == "conversation_fulfillment.v1"
    assert contract["required_fields"] == [
        "fulfilled_goal",
        "fulfilled_steps",
        "pending_steps",
        "failed_steps",
        "recovery_actions",
        "fulfillment_confidence",
        "completion_reason",
    ]
    assert contract["turn_scoped_projection"] == "conversation_fulfillment"


def test_contact_timing_question_closes_conversational_goal_without_extra_question():
    runtime = build_galicia_runtime()

    state = _run(runtime, "ful-contact", "Cuando me van a contactar?")
    fulfillment = _fulfillment(state)

    assert fulfillment["fulfilled_goal"]["status"] == "fulfilled"
    assert fulfillment["pending_steps"] == []
    assert fulfillment["failed_steps"] == []
    assert _actions(fulfillment) == ["close_objective"]
    assert fulfillment["completion_reason"] == "conversation_goal_fulfilled"
    assert fulfillment["fulfillment_confidence"] >= 0.9
    assert "La denuncia ya esta cargada?" not in state.response


def test_slot_answer_partially_fulfills_turn_and_keeps_next_step_pending():
    runtime = build_galicia_runtime()
    _run(runtime, "ful-partial", "Me chocaron ayer")

    state = _run(runtime, "ful-partial", "No hubo lesionados.")
    fulfillment = _fulfillment(state)

    assert fulfillment["fulfilled_goal"]["status"] == "partially_fulfilled"
    assert "confirm_injuries" in _step_ids(fulfillment["fulfilled_steps"])
    assert "confirm_user_role" in _step_ids(fulfillment["pending_steps"])
    assert fulfillment["failed_steps"] == []
    assert _actions(fulfillment) == ["continue_with_next_pending_step"]
    assert "Sos asegurado de Galicia o tercero damnificado?" in state.response


def test_unanswered_expected_step_records_failure_and_recovery_action():
    runtime = build_galicia_runtime()
    _run(runtime, "ful-recovery", "Me chocaron ayer")

    state = _run(runtime, "ful-recovery", "El auto es rojo.")
    fulfillment = _fulfillment(state)

    assert fulfillment["fulfilled_goal"]["status"] == "failed"
    assert _step_ids(fulfillment["failed_steps"]) == ["confirm_injuries"]
    assert _actions(fulfillment) == ["reask_or_reformulate"]
    assert fulfillment["recovery_actions"][0]["target_step"]["id"] == "confirm_injuries"
    assert fulfillment["completion_reason"] == "expected_step_not_satisfied_recovery_selected"
    assert "Hubo lesionados?" in state.response


def test_lateral_question_is_fulfilled_and_main_plan_is_resumed():
    runtime = build_galicia_runtime()
    _run(runtime, "ful-lateral", "Me chocaron ayer")
    _run(runtime, "ful-lateral", "No hubo lesionados.")

    state = _run(runtime, "ful-lateral", "Y cuanto tarda normalmente?")
    fulfillment = _fulfillment(state)

    assert fulfillment["fulfilled_goal"]["status"] == "partially_fulfilled"
    assert "answer_lateral_process_timing" in _step_ids(fulfillment["fulfilled_steps"])
    assert "confirm_user_role" in _step_ids(fulfillment["pending_steps"])
    assert _actions(fulfillment) == ["resume_main_plan"]
    assert fulfillment["completion_reason"] == "lateral_question_fulfilled_main_plan_resumed"
    assert "Sobre los tiempos" in state.response
    assert "Sos asegurado de Galicia o tercero damnificado?" in state.response


def test_conversation_fulfillment_is_available_in_runtime_record():
    runtime = build_galicia_runtime()

    state = _run(runtime, "ful-observable", "Me chocaron ayer")
    runtime_record = state.facts["conversation_state_runtime"]

    assert state.facts["conversation_fulfillment"]["fulfillment"]["contract"] == "conversation_fulfillment.v1"
    assert runtime_record["conversation_fulfillment"]["fulfillment"]["fulfilled_goal"]["status"] == "partially_fulfilled"
    assert any(
        projection["reason"] == "conversation_plan_fulfillment"
        for projection in runtime_record["projections"]
    )
