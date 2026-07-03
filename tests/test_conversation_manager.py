from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.conversation_manager import ConversationManager


def test_conversation_manager_opens_session_and_tracks_turns():
    manager = ConversationManager()
    event = Event(
        type="user_message",
        payload="Hola",
        metadata={"conversation_id": "conv-1"},
    )

    state = manager.before_process(event)

    assert state.conversation_id == "conv-1"

    session = manager.get_session("conv-1")
    assert session is not None
    assert session.status == "open"
    assert len(session.turns) == 1
    assert session.turns[0].normalized_payload == "hola"


def test_conversation_manager_preserves_existing_state_conversation():
    manager = ConversationManager()
    state = CognitiveState(conversation_id="conv-2")
    event = Event(type="user_message", payload="Me chocaron")

    next_state = manager.before_process(event, state)

    assert next_state.conversation_id == "conv-2"
    assert manager.get_session("conv-2") is not None


def test_conversation_manager_closes_session():
    manager = ConversationManager()
    manager.open("conv-3")
    manager.close("conv-3")

    assert manager.get_session("conv-3").status == "closed"