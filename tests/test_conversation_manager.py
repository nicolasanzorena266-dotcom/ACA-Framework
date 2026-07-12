from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.conversation_manager import ConversationManager
from aca_os.conversation_state import ConversationState


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
    assert manager.conversation_state("conv-2").conversation_id == "conv-2"


def test_conversation_manager_closes_session():
    manager = ConversationManager()
    manager.open("conv-3")
    manager.close("conv-3")

    assert manager.get_session("conv-3").status == "closed"


def test_conversation_manager_operationally_loads_and_commits_conversation_state():
    manager = ConversationManager()
    session = manager.open("conv-4")
    session.conversation_state = ConversationState(
        conversation_id="conv-4",
        active_mission={"type": "auto_claim_guidance", "goal": "orientar", "missing": ["injuries"]},
        confirmed_facts={"event_type": "vehicle_collision"},
    )

    turn = manager.begin_turn(Event(type="user_message", payload="sigo", metadata={"conversation_id": "conv-4"}))

    assert turn.conversation_state.active_mission["type"] == "auto_claim_guidance"
    assert turn.cognitive_state.active_mission["type"] == "auto_claim_guidance"
    assert turn.cognitive_state.facts["event_type"] == "vehicle_collision"

    final_state = turn.cognitive_state.evolve(
        "TEST_MUTATION",
        facts={**turn.cognitive_state.facts, "event_date": "relative:yesterday"},
    )
    manager.after_process(final_state)
    committed = manager.conversation_state("conv-4")
    record = manager.conversation_state_runtime_record("conv-4")

    assert committed.confirmed_facts["event_date"] == "relative:yesterday"
    assert record["operational_owner"] == "conversation_manager"
    assert any(change["field"] == "confirmed_facts" for change in record["changes"])
    assert record["projections"][0]["direction"] == "ConversationState -> CognitiveState"
