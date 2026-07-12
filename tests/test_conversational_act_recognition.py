from aca_kernel.core.events import Event
from aca_os.conversation_state import (
    ConversationalActType,
    conversational_act_contract,
)
from sdk.factory import build_galicia_runtime


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _conversation(runtime, conversation_id: str):
    return runtime.conversation_manager.conversation_state(conversation_id)


def _act(runtime, conversation_id: str):
    return _conversation(runtime, conversation_id).last_conversational_act


def test_conversational_act_contract_is_explicit():
    contract = conversational_act_contract()

    assert contract["contract"] == "conversational_act.v1"
    assert ConversationalActType.PENDING_ANSWER in contract["act_types"]
    assert ConversationalActType.SIMPLIFICATION_REQUEST in contract["act_types"]
    assert ConversationalActType.RECAP_REQUEST in contract["act_types"]
    assert "impact" in contract["required_fields"]


def test_minimal_yes_answers_pending_question_instead_of_new_intent():
    runtime = build_galicia_runtime()
    _run(runtime, "act-pending-yes", "Me chocaron ayer")
    _run(runtime, "act-pending-yes", "No")

    state = _run(runtime, "act-pending-yes", "Si.")
    act = _act(runtime, "act-pending-yes")

    assert act["act"] == ConversationalActType.PENDING_ANSWER
    assert act["target"]["primary_slot"] == "user_role"
    assert act["confidence"] >= 0.8
    assert state.intent_match["intent"] == "auto_claim_guidance"
    assert state.intent_match["reason"] == "pending_question_answer"
    assert _conversation(runtime, "act-pending-yes").confirmed_facts["user_role"]["value"] == "insured"


def test_minimal_yes_outside_pending_question_is_confirmation_not_pending_answer():
    runtime = build_galicia_runtime()

    state = _run(runtime, "act-confirmation", "Si.")
    act = _act(runtime, "act-confirmation")

    assert act["act"] == ConversationalActType.CONFIRMATION
    assert act["confidence"] >= 0.7
    assert act["impact"]["may_confirm_previous_act"] is True
    assert "conversation_slot_resolution" not in state.facts


def test_simplification_request_preserves_mission_and_reinterprets_response():
    runtime = build_galicia_runtime()
    _run(runtime, "act-simple", "Me chocaron ayer")
    _run(runtime, "act-simple", "No")
    _run(runtime, "act-simple", "Soy asegurado.")

    state = _run(runtime, "act-simple", "Explicamelo mas simple.")
    conversation = _conversation(runtime, "act-simple")
    act = conversation.last_conversational_act

    assert act["act"] == ConversationalActType.SIMPLIFICATION_REQUEST
    assert state.intent_match["intent"] == "auto_claim_guidance"
    assert state.intent_match["reason"] == "conversation_act_simplification_request"
    assert conversation.active_mission["type"] == "auto_claim_guidance"
    assert conversation.active_mission["next_act"] == "check_claim_report_loaded"
    assert "Mas simple" in state.response
    assert "denuncia ya esta cargada" in state.response


def test_recap_request_is_registered_without_restarting_mission():
    runtime = build_galicia_runtime()
    _run(runtime, "act-recap", "Me chocaron ayer")
    _run(runtime, "act-recap", "No")
    _run(runtime, "act-recap", "Soy asegurado.")

    state = _run(runtime, "act-recap", "Resumime.")
    conversation = _conversation(runtime, "act-recap")

    assert conversation.last_conversational_act["act"] == ConversationalActType.RECAP_REQUEST
    assert state.facts["conversation_act"]["act"] == ConversationalActType.RECAP_REQUEST
    assert state.intent_match["reason"] == "conversation_act_recap_request"
    assert conversation.active_mission["type"] == "auto_claim_guidance"
    assert "Resumen breve" in state.response


def test_topic_shift_request_is_recognized_as_conversation_flow_control():
    runtime = build_galicia_runtime()
    _run(runtime, "act-topic", "Me chocaron ayer")
    _run(runtime, "act-topic", "No")

    state = _run(runtime, "act-topic", "Volvamos a lo anterior.")
    conversation = _conversation(runtime, "act-topic")

    assert conversation.last_conversational_act["act"] == ConversationalActType.TOPIC_SHIFT
    assert state.intent_match["reason"] == "conversation_act_topic_shift"
    assert conversation.active_mission["type"] == "auto_claim_guidance"
    assert "Retomo el tema anterior" in state.response


def test_continuation_keeps_existing_mission_active():
    runtime = build_galicia_runtime()
    _run(runtime, "act-continue", "Me chocaron ayer")
    _run(runtime, "act-continue", "No")
    _run(runtime, "act-continue", "Soy asegurado.")

    state = _run(runtime, "act-continue", "Seguimos.")
    conversation = _conversation(runtime, "act-continue")

    assert conversation.last_conversational_act["act"] == ConversationalActType.CONTINUATION
    assert state.intent_match["reason"] == "conversation_act_continuation"
    assert conversation.active_mission["next_act"] == "check_claim_report_loaded"
    assert "denuncia ya esta cargada" in state.response


def test_correction_act_wins_over_negation_when_prior_fact_exists():
    runtime = build_galicia_runtime()
    _run(runtime, "act-correction", "Me chocaron ayer")
    _run(runtime, "act-correction", "No")
    _run(runtime, "act-correction", "Soy asegurado.")

    state = _run(runtime, "act-correction", "No, soy tercero.")
    act = _act(runtime, "act-correction")

    assert act["act"] == ConversationalActType.CORRECTION
    assert act["target"]["facts"] == ["user_role"]
    assert any(item["act"] == ConversationalActType.NEGATION for item in act["alternatives"])
    assert state.facts["conversation_fact_revision"]["revisions"][0]["fact"]["type"] == "user_role"


def test_ambiguous_control_turn_records_candidates_without_inventing_revision():
    runtime = build_galicia_runtime()
    _run(runtime, "act-ambiguous", "Me chocaron ayer")
    _run(runtime, "act-ambiguous", "No hubo lesionados y soy asegurado.")

    state = _run(runtime, "act-ambiguous", "Me confundi.")
    act = _act(runtime, "act-ambiguous")

    assert act["act"] == ConversationalActType.CORRECTION
    assert act["impact"]["requires_clarification"] is True
    assert state.facts["conversation_fact_revision"]["ambiguous_revisions"][0]["candidate_facts"] == ["injuries", "user_role"]
    assert "conversation_slot_resolution" not in state.facts
    assert "que dato cambiamos" in state.response


def test_no_me_equivoque_is_correction_even_without_explicit_fact_target():
    runtime = build_galicia_runtime()
    _run(runtime, "act-no-mistake", "Me chocaron ayer")
    _run(runtime, "act-no-mistake", "No hubo lesionados y soy asegurado.")

    state = _run(runtime, "act-no-mistake", "No, me equivoque.")
    act = _act(runtime, "act-no-mistake")

    assert act["act"] == ConversationalActType.CORRECTION
    assert act["impact"]["requires_clarification"] is True
    assert state.facts["conversation_fact_revision"]["ambiguous_revisions"][0]["candidate_facts"] == ["injuries", "user_role"]
