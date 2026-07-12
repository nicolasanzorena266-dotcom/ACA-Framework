from aca_kernel.core.events import Event
from aca_os.conversation_state import SLOT_CLOSED_STATUSES, SLOT_LIFECYCLE, SlotStatus, slot_lifecycle_contract
from sdk.factory import build_galicia_runtime


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _conversation(runtime, conversation_id: str):
    return runtime.conversation_manager.conversation_state(conversation_id)


def test_slot_lifecycle_contract_is_explicit():
    contract = slot_lifecycle_contract()

    assert contract["contract"] == "slot_lifecycle.v1"
    assert SlotStatus.PENDING in contract["statuses"]
    assert SlotStatus.ANSWERED in SLOT_LIFECYCLE[SlotStatus.PENDING]
    assert SlotStatus.ANSWERED in SLOT_CLOSED_STATUSES
    assert SlotStatus.REFUTED in SLOT_CLOSED_STATUSES


def test_direct_answer_resolves_pending_injuries_question():
    runtime = build_galicia_runtime()
    _run(runtime, "slot-direct", "Me chocaron ayer")

    state = _run(runtime, "slot-direct", "No.")
    conversation = _conversation(runtime, "slot-direct")
    resolution = state.facts["conversation_slot_resolution"]["resolutions"][0]

    assert conversation.slots["injuries"]["status"] == SlotStatus.ANSWERED
    assert conversation.slots["injuries"]["value"] is False
    assert conversation.pending_questions[0]["slot"] == "user_role"
    assert "ask_if_injuries" not in state.plan
    assert "ask_user_role" in state.plan
    assert "lesionados?" not in state.response.lower()
    assert resolution["slot"] == "injuries"
    assert resolution["from_status"] == SlotStatus.PENDING
    assert resolution["to_status"] == SlotStatus.ANSWERED
    assert resolution["closed"] is True
    assert resolution["confidence"] >= 0.8


def test_contextual_yes_resolves_user_role_after_pending_question():
    runtime = build_galicia_runtime()
    _run(runtime, "slot-implicit", "Me chocaron ayer")
    _run(runtime, "slot-implicit", "No")

    state = _run(runtime, "slot-implicit", "Si")
    conversation = _conversation(runtime, "slot-implicit")

    assert conversation.slots["user_role"]["status"] == SlotStatus.ANSWERED
    assert conversation.slots["user_role"]["value"] == "insured"
    assert conversation.pending_questions == []
    assert state.plan == []
    assert "denuncia ya esta cargada" in state.response
    assert state.intent_match["reason"] == "pending_question_answer"


def test_multiple_slot_answers_close_all_matching_pending_questions():
    runtime = build_galicia_runtime()
    _run(runtime, "slot-multiple", "Me chocaron ayer")

    state = _run(runtime, "slot-multiple", "No hubo lesionados y soy asegurado.")
    conversation = _conversation(runtime, "slot-multiple")
    resolutions = state.facts["conversation_slot_resolution"]["resolutions"]

    assert conversation.slots["injuries"]["value"] is False
    assert conversation.slots["user_role"]["value"] == "insured"
    assert conversation.pending_questions == []
    assert {resolution["slot"] for resolution in resolutions} == {"injuries", "user_role"}
    assert state.plan == []


def test_out_of_order_answer_fills_target_slot_and_keeps_other_pending():
    runtime = build_galicia_runtime()
    _run(runtime, "slot-out-of-order", "Me chocaron ayer")

    state = _run(runtime, "slot-out-of-order", "Soy tercero damnificado.")
    conversation = _conversation(runtime, "slot-out-of-order")

    assert conversation.slots["user_role"]["status"] == SlotStatus.ANSWERED
    assert conversation.slots["user_role"]["value"] == "third_party"
    assert conversation.slots["injuries"]["status"] == SlotStatus.PENDING
    assert [question["slot"] for question in conversation.pending_questions] == ["injuries"]
    assert state.plan == ["ask_if_injuries"]
    assert "resulto herida" in state.response.lower()


def test_ambiguous_answer_partially_fills_slot_without_closing_question():
    runtime = build_galicia_runtime()
    _run(runtime, "slot-ambiguous", "Me chocaron ayer")

    state = _run(runtime, "slot-ambiguous", "No estoy seguro.")
    conversation = _conversation(runtime, "slot-ambiguous")
    resolution = state.facts["conversation_slot_resolution"]["resolutions"][0]

    assert conversation.slots["injuries"]["status"] == SlotStatus.PARTIALLY_FILLED
    assert conversation.slots["injuries"]["value"] == "unknown"
    assert [question["slot"] for question in conversation.pending_questions] == ["injuries", "user_role"]
    assert resolution["closed"] is False
    assert resolution["to_status"] == SlotStatus.PARTIALLY_FILLED


def test_repeated_answer_does_not_reopen_closed_slot_and_continues_pending_flow():
    runtime = build_galicia_runtime()
    _run(runtime, "slot-repeated", "Me chocaron ayer")
    _run(runtime, "slot-repeated", "No")

    state = _run(runtime, "slot-repeated", "No")
    conversation = _conversation(runtime, "slot-repeated")
    resolution = state.facts["conversation_slot_resolution"]["resolutions"][0]

    assert conversation.slots["injuries"]["status"] == SlotStatus.ANSWERED
    assert conversation.slots["injuries"]["value"] is False
    assert conversation.slots["user_role"]["status"] == SlotStatus.PENDING
    assert resolution["repeated"] is True
    assert state.intent_match["reason"] == "pending_question_answer"
    assert state.plan == ["ask_user_role"]


def test_answer_for_already_resolved_questions_does_not_create_pending_question():
    runtime = build_galicia_runtime()
    _run(runtime, "slot-resolved", "Me chocaron ayer")
    _run(runtime, "slot-resolved", "No")
    _run(runtime, "slot-resolved", "Soy asegurado")

    state = _run(runtime, "slot-resolved", "No")
    conversation = _conversation(runtime, "slot-resolved")
    resolution = state.facts["conversation_slot_resolution"]["resolutions"][0]

    assert conversation.pending_questions == []
    assert conversation.slots["injuries"]["status"] == SlotStatus.ANSWERED
    assert conversation.slots["user_role"]["status"] == SlotStatus.ANSWERED
    assert resolution["repeated"] is True
    assert "lesionados?" not in state.response.lower()
