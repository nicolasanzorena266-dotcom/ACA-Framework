from aca_kernel.core.events import Event
from aca_os.conversation_state import FactStatus, MissionLifecycleStatus, fact_lifecycle_contract
from sdk.factory import build_galicia_runtime


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _conversation(runtime, conversation_id: str):
    return runtime.conversation_manager.conversation_state(conversation_id)


def test_fact_lifecycle_contract_supports_revision_states():
    contract = fact_lifecycle_contract()

    assert contract["contract"] == "fact_lifecycle.v1"
    assert contract["active_statuses"] == [FactStatus.ACTIVE]
    assert FactStatus.SUPERSEDED in contract["transitions"][FactStatus.ACTIVE]
    assert FactStatus.REFUTED in contract["transitions"][FactStatus.ACTIVE]
    assert FactStatus.WITHDRAWN in contract["transitions"][FactStatus.ACTIVE]


def test_injuries_correction_refutes_previous_fact_and_updates_mission():
    runtime = build_galicia_runtime()
    _run(runtime, "revision-injuries", "Me chocaron ayer")
    _run(runtime, "revision-injuries", "No hubo lesionados.")
    _run(runtime, "revision-injuries", "Soy asegurado.")

    state = _run(runtime, "revision-injuries", "Perdon, si hubo lesionados.")
    conversation = _conversation(runtime, "revision-injuries")
    active = conversation.confirmed_facts["injuries"]
    inactive = conversation.refuted_facts["injuries"][0]
    revision = state.facts["conversation_fact_revision"]

    assert active["status"] == FactStatus.ACTIVE
    assert active["value"] is True
    assert active["revision_reason"] == "user_corrected_previous_negation"
    assert active["replaced_fact"]["value"] is False
    assert active["history"][0]["status"] == FactStatus.REFUTED
    assert inactive["status"] == FactStatus.REFUTED
    assert inactive["value"] is False
    assert conversation.slots["injuries"]["value"] is True
    assert conversation.active_mission["facts"]["injuries"]["value"] is True
    assert conversation.active_mission["next_act"] == "prioritize_injury_assistance"
    assert revision["revisions"][0]["revision"]["transition"] == "refuted->active"
    assert revision["affected_slots"] == ["injuries"]
    assert "hubo lesionados" in state.response


def test_user_role_replacement_supersedes_previous_active_fact():
    runtime = build_galicia_runtime()
    _run(runtime, "revision-role", "Me chocaron ayer")
    _run(runtime, "revision-role", "No")
    _run(runtime, "revision-role", "Soy asegurado.")

    state = _run(runtime, "revision-role", "No, soy tercero.")
    conversation = _conversation(runtime, "revision-role")
    active = conversation.confirmed_facts["user_role"]
    inactive = conversation.refuted_facts["user_role"][0]

    assert active["status"] == FactStatus.ACTIVE
    assert active["value"] == "third_party"
    assert active["revision_reason"] == "user_replaced_previous_fact"
    assert active["history"][0]["value"] == "insured"
    assert inactive["status"] == FactStatus.SUPERSEDED
    assert inactive["value"] == "insured"
    assert conversation.slots["user_role"]["value"] == "third_party"
    assert conversation.active_mission["facts"]["user_role"]["value"] == "third_party"
    assert state.facts["conversation_fact_revision"]["revisions"][0]["fact"]["type"] == "user_role"
    assert len([key for key in conversation.confirmed_facts if key == "user_role"]) == 1


def test_claim_report_correction_returns_mission_to_required_step():
    runtime = build_galicia_runtime()
    _run(runtime, "revision-report", "Me chocaron ayer")
    _run(runtime, "revision-report", "No")
    _run(runtime, "revision-report", "Soy asegurado.")
    _run(runtime, "revision-report", "La denuncia ya esta cargada.")

    state = _run(runtime, "revision-report", "Perdon, todavia no.")
    conversation = _conversation(runtime, "revision-report")
    active = conversation.confirmed_facts["claim_report_loaded"]
    inactive = conversation.refuted_facts["claim_report_loaded"][0]
    advancement = state.facts["conversation_mission_advancement"]

    assert active["status"] == FactStatus.ACTIVE
    assert active["value"] is False
    assert inactive["status"] == FactStatus.REFUTED
    assert inactive["value"] is True
    assert conversation.active_mission["next_act"] == "check_claim_report_loaded"
    assert conversation.active_mission["lifecycle_status"] == MissionLifecycleStatus.READY_TO_PROGRESS
    assert conversation.active_mission["facts"]["claim_report_loaded"]["value"] is False
    assert advancement["reason"] == "core_slots_answered_check_claim_report"
    assert "todavia no esta cargada" in state.response


def test_clear_generic_withdrawal_removes_latest_fact_without_leaving_active_duplicate():
    runtime = build_galicia_runtime()
    _run(runtime, "revision-withdraw", "Me chocaron ayer")
    _run(runtime, "revision-withdraw", "No")
    _run(runtime, "revision-withdraw", "Soy asegurado.")
    _run(runtime, "revision-withdraw", "La denuncia ya esta cargada.")

    state = _run(runtime, "revision-withdraw", "Me confundi.")
    conversation = _conversation(runtime, "revision-withdraw")
    withdrawal = state.facts["conversation_fact_revision"]["withdrawals"][0]

    assert "claim_report_loaded" not in conversation.confirmed_facts
    assert conversation.refuted_facts["claim_report_loaded"][0]["status"] == FactStatus.WITHDRAWN
    assert withdrawal["fact_type"] == "claim_report_loaded"
    assert conversation.active_mission["next_act"] == "check_claim_report_loaded"
    assert "denuncia ya esta cargada" in state.response


def test_ambiguous_withdrawal_requests_clarification_without_changing_active_facts():
    runtime = build_galicia_runtime()
    _run(runtime, "revision-ambiguous", "Me chocaron ayer")
    _run(runtime, "revision-ambiguous", "No hubo lesionados y soy asegurado.")

    state = _run(runtime, "revision-ambiguous", "Me confundi.")
    conversation = _conversation(runtime, "revision-ambiguous")
    revision = state.facts["conversation_fact_revision"]

    assert conversation.confirmed_facts["injuries"]["value"] is False
    assert conversation.confirmed_facts["user_role"]["value"] == "insured"
    assert conversation.refuted_facts == {}
    assert revision["ambiguous_revisions"][0]["candidate_facts"] == ["injuries", "user_role"]
    assert conversation.active_mission["next_act"] == "clarify_fact_revision"
    assert "que dato cambiamos" in state.response


def test_multiple_corrections_preserve_history_without_multiple_active_facts():
    runtime = build_galicia_runtime()
    _run(runtime, "revision-multiple", "Me chocaron ayer")
    _run(runtime, "revision-multiple", "No")
    _run(runtime, "revision-multiple", "Soy asegurado.")
    _run(runtime, "revision-multiple", "Perdon, si hubo lesionados.")

    state = _run(runtime, "revision-multiple", "No, soy tercero.")
    conversation = _conversation(runtime, "revision-multiple")

    assert conversation.confirmed_facts["injuries"]["value"] is True
    assert conversation.confirmed_facts["user_role"]["value"] == "third_party"
    assert conversation.confirmed_facts["injuries"]["status"] == FactStatus.ACTIVE
    assert conversation.confirmed_facts["user_role"]["status"] == FactStatus.ACTIVE
    assert conversation.refuted_facts["injuries"][0]["value"] is False
    assert conversation.refuted_facts["user_role"][0]["value"] == "insured"
    assert state.facts["conversation_fact_revision"]["revisions"][0]["fact"]["type"] == "user_role"
