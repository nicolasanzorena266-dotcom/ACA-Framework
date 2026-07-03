from dataclasses import dataclass, field
from typing import Dict, List

from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.text import normalize_text


@dataclass(frozen=True)
class ConversationTurn:
    event_id: str
    event_type: str
    payload: str
    normalized_payload: str


@dataclass
class ConversationSession:
    id: str
    status: str = "open"
    turns: List[ConversationTurn] = field(default_factory=list)
    active_state: CognitiveState | None = None

    def add_turn(self, event: Event) -> None:
        self.turns.append(
            ConversationTurn(
                event_id=event.id,
                event_type=event.type,
                payload=str(event.payload),
                normalized_payload=normalize_text(event.payload),
            )
        )


class ConversationManager:
    """Owns conversation lifecycle.

    The Conversation Manager does not interpret insurance content.
    It tracks session continuity and provides the active CSM to the runtime.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, ConversationSession] = {}

    def open(self, conversation_id: str) -> ConversationSession:
        if conversation_id not in self._sessions:
            self._sessions[conversation_id] = ConversationSession(id=conversation_id)
        return self._sessions[conversation_id]

    def before_process(
        self,
        event: Event,
        state: CognitiveState | None = None,
    ) -> CognitiveState:
        conversation_id = state.conversation_id if state else event.metadata.get("conversation_id", "default")
        session = self.open(conversation_id)
        session.add_turn(event)
        return state or CognitiveState(conversation_id=conversation_id)

    def after_process(self, state: CognitiveState) -> CognitiveState:
        session = self.open(state.conversation_id)
        session.active_state = state
        return state

    def get_session(self, conversation_id: str) -> ConversationSession | None:
        return self._sessions.get(conversation_id)

    def close(self, conversation_id: str) -> None:
        session = self.open(conversation_id)
        session.status = "closed"