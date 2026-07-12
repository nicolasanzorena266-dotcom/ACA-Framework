from dataclasses import dataclass, field, replace
from typing import Any, Dict, List

from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_core.text import normalize_text
from aca_os.conversation_state import ConversationState, conversation_state_diff


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
    conversation_state: ConversationState | None = None
    turn_started_state: ConversationState | None = None
    last_state_changes: list[Dict[str, Any]] = field(default_factory=list)
    last_projection_log: list[Dict[str, Any]] = field(default_factory=list)

    def add_turn(self, event: Event) -> None:
        self.turns.append(
            ConversationTurn(
                event_id=event.id,
                event_type=event.type,
                payload=str(event.payload),
                normalized_payload=normalize_text(event.payload),
            )
        )


@dataclass(frozen=True)
class ConversationTurnContext:
    conversation_id: str
    conversation_state: ConversationState
    cognitive_state: CognitiveState
    projections: tuple[Dict[str, Any], ...]
    slot_resolutions: tuple[Dict[str, Any], ...] = ()
    fact_assimilations: tuple[Dict[str, Any], ...] = ()
    fact_revisions: tuple[Dict[str, Any], ...] = ()
    mission_advancement: Dict[str, Any] | None = None


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
        return self.begin_turn(event, state).cognitive_state

    def begin_turn(
        self,
        event: Event,
        state: CognitiveState | None = None,
    ) -> ConversationTurnContext:
        conversation_id = state.conversation_id if state else event.metadata.get("conversation_id", "default")
        session = self.open(conversation_id)
        session.add_turn(event)
        initial = self._load_conversation_state(session, state=state)
        initial = replace(
            initial,
            turn_count=len(session.turns),
            derived_state=without_turn_scoped_derived_state(initial.derived_state),
            projection_sources=_append_unique(initial.projection_sources, "conversation_manager.begin_turn"),
        )
        turn_started_state = initial
        resolved, slot_resolutions = initial.resolve_pending_slot_answers(event.payload)
        initial = resolved
        initial, fact_assimilations, mission_advancement = initial.assimilate_user_facts(event.payload)
        cognitive_state = initial.to_cognitive_state(
            base=state,
            source="conversation_manager.begin_turn",
        )
        projections = (
            {
                "component": "conversation_manager",
                "direction": "ConversationState -> CognitiveState",
                "reason": "runtime_turn_start",
                "source_contract": initial.contract,
                "target": "CognitiveState",
            },
        )
        session.conversation_state = initial
        session.turn_started_state = turn_started_state
        session.last_state_changes = []
        session.last_projection_log = [dict(projection) for projection in projections]
        if slot_resolutions:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "UserMessage -> ConversationState",
                    "reason": "pending_question_resolution",
                    "resolved_slots": [resolution["slot"] for resolution in slot_resolutions],
                }
            )
        if fact_assimilations:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "UserMessage -> ConversationalFact",
                    "reason": "fact_assimilation",
                    "facts": [item["fact"]["type"] for item in fact_assimilations if item.get("fact")],
                }
            )
        fact_revision = initial.derived_state.get("fact_revision")
        fact_revisions = []
        if isinstance(fact_revision, dict):
            fact_revisions = list(fact_revision.get("revisions") or []) + list(fact_revision.get("withdrawals") or [])
            fact_revisions += list(fact_revision.get("ambiguous_revisions") or [])
        if fact_revision:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "UserMessage -> ConversationalFact",
                    "reason": "fact_revision",
                    "revisions": [
                        item.get("fact", {}).get("type") or item.get("fact_type")
                        for item in fact_revisions
                    ],
                    "ambiguous": bool(fact_revision.get("ambiguous_revisions")),
                }
            )
        if mission_advancement:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "ConversationalFact -> Mission",
                    "reason": "mission_advancement",
                    "from_status": mission_advancement.get("from_status"),
                    "to_status": mission_advancement.get("to_status"),
                    "next_act": mission_advancement.get("next_act"),
                }
            )
        return ConversationTurnContext(
            conversation_id=conversation_id,
            conversation_state=initial,
            cognitive_state=cognitive_state,
            projections=projections,
            slot_resolutions=tuple(dict(resolution) for resolution in slot_resolutions),
            fact_assimilations=tuple(dict(item) for item in fact_assimilations),
            fact_revisions=tuple(dict(item) for item in fact_revisions),
            mission_advancement=dict(mission_advancement) if mission_advancement else None,
        )

    def after_process(self, state: CognitiveState) -> CognitiveState:
        session = self.open(state.conversation_id)
        session.active_state = state
        final_projection = ConversationState.from_cognitive_state(
            state,
            turn_count=len(session.turns),
            source="conversation_manager.after_process",
        )
        final_state = self._merge_with_existing_conversation_state(
            final_projection,
            previous=session.conversation_state,
        )
        mutations = conversation_state_diff(session.turn_started_state, final_state)
        session.conversation_state = final_state
        session.last_state_changes = [mutation.to_dict() for mutation in mutations]
        session.last_projection_log.append(
            {
                "component": "conversation_manager",
                "direction": "CognitiveState -> ConversationState",
                "reason": "runtime_turn_commit",
                "source": "CognitiveState",
                "target_contract": final_state.contract,
            }
        )
        return state

    def get_session(self, conversation_id: str) -> ConversationSession | None:
        return self._sessions.get(conversation_id)

    def conversation_state(self, conversation_id: str):
        session = self.get_session(conversation_id)
        if session is None:
            return ConversationState(conversation_id=conversation_id, projection_sources=("conversation_manager",))
        if session.conversation_state is not None:
            return session.conversation_state
        if session.active_state is None:
            return ConversationState(
                conversation_id=session.id,
                turn_count=len(session.turns),
                projection_sources=("conversation_manager",),
            )
        return ConversationState.from_cognitive_state(
            session.active_state,
            turn_count=len(session.turns),
            source="conversation_manager.active_state",
        )

    def project_from_cognitive_state(self, state: CognitiveState, *, source: str) -> ConversationState:
        session = self.open(state.conversation_id)
        projection = ConversationState.from_cognitive_state(
            state,
            turn_count=len(session.turns),
            source=source,
        )
        merged = self._merge_with_existing_conversation_state(
            projection,
            previous=session.conversation_state,
        )
        return merged

    def conversation_state_runtime_record(self, conversation_id: str) -> Dict[str, Any]:
        session = self.get_session(conversation_id)
        if session is None:
            return {
                "contract": "conversation_state_runtime.v1",
                "operational_owner": "conversation_manager",
                "conversation_id": conversation_id,
                "available": False,
            }
        initial = session.turn_started_state
        final = session.conversation_state
        return {
            "contract": "conversation_state_runtime.v1",
            "available": final is not None,
            "operational_owner": "conversation_manager",
            "conversation_id": conversation_id,
            "turn_count": len(session.turns),
            "initial_state": initial.to_dict() if initial else {},
            "final_state": final.to_dict() if final else {},
            "changes": [dict(change) for change in session.last_state_changes],
            "fact_assimilation": (final.derived_state or {}).get("fact_assimilation", {}) if final else {},
            "fact_revision": (final.derived_state or {}).get("fact_revision", {}) if final else {},
            "mission_advancement": (final.derived_state or {}).get("mission_advancement", {}) if final else {},
            "projections": [dict(projection) for projection in session.last_projection_log],
            "modifying_components": sorted(
                {
                    str(change.get("component"))
                    for change in session.last_state_changes
                    if change.get("component")
                }
            ),
            "legacy_projection_targets": ["CognitiveState", "PublicConversationState"],
        }

    def close(self, conversation_id: str) -> None:
        session = self.open(conversation_id)
        session.status = "closed"

    def _load_conversation_state(
        self,
        session: ConversationSession,
        *,
        state: CognitiveState | None,
    ) -> ConversationState:
        if state is not None:
            return ConversationState.from_cognitive_state(
                state,
                turn_count=len(session.turns),
                source="provided_cognitive_state",
            )
        if session.conversation_state is not None:
            return session.conversation_state
        if session.active_state is not None:
            return ConversationState.from_cognitive_state(
                session.active_state,
                turn_count=len(session.turns),
                source="conversation_manager.active_state_bootstrap",
            )
        return ConversationState(
            conversation_id=session.id,
            turn_count=len(session.turns),
            projection_sources=("conversation_manager.new_state",),
        )

    def _merge_with_existing_conversation_state(
        self,
        projection: ConversationState,
        *,
        previous: ConversationState | None,
    ) -> ConversationState:
        if previous is None:
            return projection
        return replace(
            projection,
            slots=merge_slots(previous.slots, projection.slots),
            confirmed_facts=merge_confirmed_facts(previous.confirmed_facts, projection.confirmed_facts),
            refuted_facts=deep_merge(previous.refuted_facts, projection.refuted_facts),
            conversation_summary=projection.conversation_summary or previous.conversation_summary,
            product_state=deep_merge(previous.product_state, projection.product_state),
            derived_state=merge_derived_state(previous.derived_state, projection.derived_state),
            temporary_state={},
            projection_sources=_append_unique(
                previous.projection_sources,
                *projection.projection_sources,
                "conversation_manager.operational_owner",
            ),
        )


def deep_merge(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(left or {})
    merged.update(dict(right or {}))
    return merged


TURN_SCOPED_DERIVED_STATE_KEYS = {
    "slot_resolution",
    "fact_assimilation",
    "fact_revision",
    "mission_advancement",
}


def without_turn_scoped_derived_state(values: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in dict(values or {}).items()
        if key not in TURN_SCOPED_DERIVED_STATE_KEYS
    }


def merge_derived_state(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    return deep_merge(without_turn_scoped_derived_state(left), dict(right or {}))


def merge_slots(left: Dict[str, Dict[str, Any]], right: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    merged = {name: dict(slot) for name, slot in (left or {}).items()}
    for name, slot in (right or {}).items():
        existing = merged.get(name)
        if existing and existing.get("status") in {"answered", "confirmed", "invalidated", "refuted"}:
            continue
        merged[name] = dict(slot)
    return merged


def merge_confirmed_facts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(right or {})
    for name, fact in (left or {}).items():
        if isinstance(fact, dict) and fact.get("contract") == "conversational_fact.v1":
            projected = merged.get(name)
            if projected == fact.get("value") or not (
                isinstance(projected, dict) and projected.get("contract") == "conversational_fact.v1"
            ):
                merged[name] = dict(fact)
    return merged


def _append_unique(values: tuple[str, ...], *extra: str) -> tuple[str, ...]:
    ordered = list(values)
    for value in extra:
        if value and value not in ordered:
            ordered.append(value)
    return tuple(ordered)
