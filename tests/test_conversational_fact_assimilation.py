from aca_kernel.core.events import Event
from aca_os.conversation_state import (
    MissionLifecycleStatus,
    fact_lifecycle_contract,
    conversational_fact_contract,
    mission_lifecycle_contract,
)
from sdk.factory import build_galicia_runtime


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _conversation(runtime, conversation_id: str):
    return runtime.conversation_manager.conversation_state(conversation_id)


def _fact(runtime, conversation_id: str, name: str):
    return _conversation(runtime, conversation_id).confirmed_facts[name]


def test_conversational_fact_and_mission_lifecycle_contracts_are_explicit():
    fact_contract = conversational_fact_contract()
    lifecycle_contract = mission_lifecycle_contract()

    assert fact_contract["contract"] == "conversational_fact.v1"
    assert fact_contract["required_fields"] == [
        "type",
        "value",
        "origin",
        "confidence",
        "mission_type",
        "acquired_turn",
        "evidence",
        "status",
        "history",
    ]
    assert fact_lifecycle_contract()["contract"] == "fact_lifecycle.v1"
    assert lifecycle_contract["contract"] == "mission_lifecycle.v1"
    assert MissionLifecycleStatus.WAITING_USER in lifecycle_contract["statuses"]
    assert MissionLifecycleStatus.READY_TO_PROGRESS in lifecycle_contract["transitions"][MissionLifecycleStatus.WAITING_USER]


def test_no_injuries_answer_becomes_conversational_fact_and_advances_mission():
    runtime = build_galicia_runtime()
    _run(runtime, "fact-injuries", "Me chocaron ayer")

    state = _run(runtime, "fact-injuries", "No hubo lesionados.")
    conversation = _conversation(runtime, "fact-injuries")
    fact = conversation.confirmed_facts["injuries"]
    assimilation = state.facts["conversation_fact_assimilation"]
    advancement = state.facts["conversation_mission_advancement"]

    assert fact["contract"] == "conversational_fact.v1"
    assert fact["type"] == "injuries"
    assert fact["value"] is False
    assert fact["origin"] in {"slot_resolution", "user_message"}
    assert fact["mission_type"] == "auto_claim_guidance"
    assert fact["acquired_turn"] == 2
    assert fact["evidence"]["normalized_message"] == "no hubo lesionados."
    assert assimilation["facts"][0]["fact"]["type"] == "injuries"
    assert conversation.active_mission["facts"]["injuries"]["value"] is False
    assert conversation.active_mission["lifecycle_status"] == MissionLifecycleStatus.WAITING_USER
    assert conversation.active_mission["next_act"] == "ask_user_role"
    assert advancement["to_status"] == MissionLifecycleStatus.WAITING_USER
    assert advancement["reason"] == "mission_waiting_for_user_role"


def test_user_role_fact_changes_expected_next_mission_step():
    runtime = build_galicia_runtime()
    _run(runtime, "fact-role", "Me chocaron ayer")
    _run(runtime, "fact-role", "No")

    state = _run(runtime, "fact-role", "Soy asegurado.")
    conversation = _conversation(runtime, "fact-role")
    fact = conversation.confirmed_facts["user_role"]
    advancement = state.facts["conversation_mission_advancement"]

    assert fact["contract"] == "conversational_fact.v1"
    assert fact["value"] == "insured"
    assert fact["origin"] in {"slot_resolution", "user_message"}
    assert conversation.pending_questions == []
    assert conversation.active_mission["lifecycle_status"] == MissionLifecycleStatus.READY_TO_PROGRESS
    assert conversation.active_mission["next_act"] == "check_claim_report_loaded"
    assert advancement["from_status"] == MissionLifecycleStatus.WAITING_USER
    assert advancement["to_status"] == MissionLifecycleStatus.READY_TO_PROGRESS
    assert advancement["reason"] == "core_slots_answered_check_claim_report"
    assert "denuncia ya esta cargada" in state.response


def test_claim_report_loaded_fact_prevents_reasking_report_and_moves_to_documentation():
    runtime = build_galicia_runtime()
    _run(runtime, "fact-report", "Me chocaron ayer")
    _run(runtime, "fact-report", "No")
    _run(runtime, "fact-report", "Soy asegurado")

    state = _run(runtime, "fact-report", "La denuncia ya esta cargada.")
    conversation = _conversation(runtime, "fact-report")
    fact = conversation.confirmed_facts["claim_report_loaded"]

    assert fact["contract"] == "conversational_fact.v1"
    assert fact["value"] is True
    assert fact["origin"] == "user_message"
    assert conversation.active_mission["facts"]["claim_report_loaded"]["value"] is True
    assert conversation.active_mission["next_act"] == "check_documentation_available"
    assert "No te la vuelvo a pedir" in state.response
    assert "documentacion" in state.response


def test_documentation_available_fact_unblocks_mission_progression():
    runtime = build_galicia_runtime()
    _run(runtime, "fact-docs", "Me chocaron ayer")
    _run(runtime, "fact-docs", "No")
    _run(runtime, "fact-docs", "Soy asegurado")
    _run(runtime, "fact-docs", "La denuncia ya esta cargada")

    state = _run(runtime, "fact-docs", "Tengo toda la documentacion.")
    conversation = _conversation(runtime, "fact-docs")
    fact = conversation.confirmed_facts["documentation_available"]
    advancement = state.facts["conversation_mission_advancement"]

    assert fact["contract"] == "conversational_fact.v1"
    assert fact["value"] is True
    assert conversation.active_mission["facts"]["documentation_available"]["value"] is True
    assert conversation.active_mission["lifecycle_status"] == MissionLifecycleStatus.PROGRESSING
    assert conversation.active_mission["next_act"] == "provide_next_step_guidance"
    assert advancement["to_status"] == MissionLifecycleStatus.PROGRESSING
    assert advancement["reason"] == "claim_report_and_documentation_ready"
    assert "Ya podemos avanzar" in state.response


def test_multiple_facts_in_one_turn_are_assimilated_before_mission_advancement():
    runtime = build_galicia_runtime()
    _run(runtime, "fact-multiple", "Me chocaron ayer")

    state = _run(runtime, "fact-multiple", "No hubo lesionados y soy asegurado.")
    conversation = _conversation(runtime, "fact-multiple")
    fact_names = {item["fact"]["type"] for item in state.facts["conversation_fact_assimilation"]["facts"]}

    assert {"injuries", "user_role"}.issubset(fact_names)
    assert conversation.confirmed_facts["injuries"]["value"] is False
    assert conversation.confirmed_facts["user_role"]["value"] == "insured"
    assert conversation.active_mission["lifecycle_status"] == MissionLifecycleStatus.READY_TO_PROGRESS
    assert conversation.active_mission["next_act"] == "check_claim_report_loaded"


def test_redundant_fact_is_observed_without_replacing_existing_fact_or_regressing_mission():
    runtime = build_galicia_runtime()
    _run(runtime, "fact-redundant", "Me chocaron ayer")
    _run(runtime, "fact-redundant", "No")
    _run(runtime, "fact-redundant", "Soy asegurado")
    _run(runtime, "fact-redundant", "La denuncia ya esta cargada")
    existing = _fact(runtime, "fact-redundant", "claim_report_loaded")

    state = _run(runtime, "fact-redundant", "La denuncia ya esta cargada.")
    conversation = _conversation(runtime, "fact-redundant")
    confirmations = state.facts["conversation_fact_assimilation"]["confirmations"]

    assert conversation.confirmed_facts["claim_report_loaded"]["value"] == existing["value"]
    assert conversation.confirmed_facts["claim_report_loaded"]["status"] == "active"
    assert conversation.confirmed_facts["claim_report_loaded"]["last_confirmed_turn"] == 5
    assert confirmations[0]["status"] == "confirmed"
    assert confirmations[0]["fact"]["type"] == "claim_report_loaded"
    assert conversation.active_mission["next_act"] == "check_documentation_available"


def test_message_without_new_fact_does_not_emit_fact_assimilation_trace():
    runtime = build_galicia_runtime()

    state = _run(runtime, "fact-noop", "Hola")
    conversation = _conversation(runtime, "fact-noop")

    assert "conversation_fact_assimilation" not in state.facts
    assert "fact_assimilation" not in conversation.derived_state
    assert "mission_advancement" not in conversation.derived_state
