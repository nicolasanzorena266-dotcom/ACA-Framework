from aca_kernel.core.events import Event
from aca_os.conversation_state import (
    ConversationalActType,
    TopicStatus,
    topic_stack_contract,
)
from sdk.factory import build_galicia_runtime


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _conversation(runtime, conversation_id: str):
    return runtime.conversation_manager.conversation_state(conversation_id)


def _active_topic(runtime, conversation_id: str):
    topics = _conversation(runtime, conversation_id).topic_stack
    for topic in reversed(topics):
        if topic.get("status") in {TopicStatus.ACTIVE, TopicStatus.RESUMED}:
            return topic
    return {}


def _prepare_claim_topic(runtime, conversation_id: str):
    _run(runtime, conversation_id, "Me chocaron ayer")
    _run(runtime, conversation_id, "No")
    _run(runtime, conversation_id, "Soy asegurado.")


def test_topic_stack_contract_is_explicit():
    contract = topic_stack_contract()

    assert contract["contract"] == "topic_stack.v1"
    assert contract["topic_contract"] == "conversation_topic.v1"
    assert TopicStatus.ACTIVE in contract["statuses"]
    assert TopicStatus.SUSPENDED in contract["statuses"]
    assert TopicStatus.RESUMED in contract["statuses"]
    assert "summary" in contract["required_topic_fields"]


def test_claim_guidance_creates_operational_active_topic():
    runtime = build_galicia_runtime()

    _run(runtime, "topic-create", "Me chocaron ayer")
    conversation = _conversation(runtime, "topic-create")
    active = _active_topic(runtime, "topic-create")

    assert conversation.topic_stack
    assert active["contract"] == "conversation_topic.v1"
    assert active["type"] == "auto_claim_guidance"
    assert active["mission_type"] == "auto_claim_guidance"
    assert active["status"] == TopicStatus.ACTIVE


def test_topic_shift_suspends_claim_topic_and_creates_new_topic():
    runtime = build_galicia_runtime()
    _prepare_claim_topic(runtime, "topic-shift")

    state = _run(runtime, "topic-shift", "Ah, otra cosa...")
    conversation = _conversation(runtime, "topic-shift")
    active = _active_topic(runtime, "topic-shift")
    suspended = [topic for topic in conversation.topic_stack if topic.get("status") == TopicStatus.SUSPENDED]

    assert conversation.last_conversational_act["act"] == ConversationalActType.TOPIC_SHIFT
    assert active["type"] == "unresolved_topic"
    assert any(topic.get("mission_type") == "auto_claim_guidance" for topic in suspended)
    assert state.facts["conversation_topic_stack"]["transition"]["type"] == "topic_switched"
    assert "Dale, contame mas" in state.response


def test_volvamos_a_denuncia_resumes_suspended_claim_topic():
    runtime = build_galicia_runtime()
    _prepare_claim_topic(runtime, "topic-denuncia")
    _run(runtime, "topic-denuncia", "Ah, otra cosa...")

    state = _run(runtime, "topic-denuncia", "Bueno, volvamos a la denuncia.")
    active = _active_topic(runtime, "topic-denuncia")
    trace = state.facts["conversation_topic_stack"]

    assert active["mission_type"] == "auto_claim_guidance"
    assert active["status"] == TopicStatus.RESUMED
    assert trace["transition"]["type"] == "topic_resumed"
    assert trace["topic_resumed"]["id"] == active["id"]
    assert "denuncia ya esta cargada" in state.response


def test_seguimos_resumes_suspended_topic():
    runtime = build_galicia_runtime()
    _prepare_claim_topic(runtime, "topic-seguimos")
    _run(runtime, "topic-seguimos", "Ah, otra cosa...")

    state = _run(runtime, "topic-seguimos", "Seguimos.")
    active = _active_topic(runtime, "topic-seguimos")

    assert state.intent_match["reason"] == "conversation_act_continuation"
    assert active["mission_type"] == "auto_claim_guidance"
    assert active["status"] == TopicStatus.RESUMED
    assert state.facts["conversation_topic_stack"]["transition"]["type"] == "topic_resumed"


def test_indirect_previous_reference_resolves_single_suspended_topic():
    runtime = build_galicia_runtime()
    _prepare_claim_topic(runtime, "topic-previous")
    _run(runtime, "topic-previous", "Ah, otra cosa...")

    state = _run(runtime, "topic-previous", "Y sobre lo anterior?")
    active = _active_topic(runtime, "topic-previous")

    assert state.facts["conversation_act"]["act"] == ConversationalActType.TOPIC_SHIFT
    assert active["mission_type"] == "auto_claim_guidance"
    assert state.facts["conversation_topic_stack"]["transition"]["type"] == "topic_resumed"


def test_topic_summary_feeds_recap_without_reconstructing_full_conversation():
    runtime = build_galicia_runtime()
    _prepare_claim_topic(runtime, "topic-summary")

    state = _run(runtime, "topic-summary", "Resumime ese tema.")
    active = _active_topic(runtime, "topic-summary")
    response_plan = state.facts["conversation_goal"]["goal"]["strategy"]["response_plan"]

    assert response_plan["available_focus"]["summary"] == active["summary"]
    assert "Resumen breve del tema activo" in state.response
    assert active["summary"] in state.response
    assert "no hubo lesionados" in state.response
    assert "sos asegurado" in state.response
