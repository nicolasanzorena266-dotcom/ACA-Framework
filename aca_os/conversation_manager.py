from dataclasses import dataclass, field, replace
from typing import Any, Dict, List

from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_core.text import normalize_text
from aca_os.conversation_state import (
    ConversationState,
    conversation_state_diff,
    conversational_goal_state_effect,
)
from aca_os.semantic_authority import (
    SemanticAuthority,
    SemanticRepresentation,
    semantic_shadow_record,
)
from aca_os.semantic_projection import (
    SemanticProjection,
    SemanticProjector,
    capture_legacy_projection,
    compare_semantic_projection,
    semantic_projection_shadow_record,
)
from aca_os.semantic_authority_pilot import (
    conversational_act_trace,
    select_conversational_act_authority,
    select_conversational_goal_authority,
    semantic_authority_pilot_enabled as semantic_authority_pilot_enabled_from_env,
    summarize_conversational_goal_authority,
    summarize_semantic_authority_pilot,
)


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
    last_semantic_representation: SemanticRepresentation | None = None
    semantic_representation_count: int = 0
    last_semantic_projection: SemanticProjection | None = None
    semantic_projection_count: int = 0
    last_semantic_failure: Dict[str, Any] | None = None
    last_legacy_conversational_act: Dict[str, Any] = field(default_factory=dict)
    last_semantic_authority_pilot: Dict[str, Any] = field(default_factory=dict)
    semantic_authority_pilot_history: List[Dict[str, Any]] = field(default_factory=list)
    last_conversational_goal_authority: Dict[str, Any] = field(default_factory=dict)
    conversational_goal_authority_history: List[Dict[str, Any]] = field(default_factory=list)

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
    conversational_act: Dict[str, Any] = field(default_factory=dict)
    conversational_goal: Dict[str, Any] = field(default_factory=dict)
    slot_resolutions: tuple[Dict[str, Any], ...] = ()
    fact_assimilations: tuple[Dict[str, Any], ...] = ()
    fact_revisions: tuple[Dict[str, Any], ...] = ()
    mission_advancement: Dict[str, Any] | None = None
    topic_transition: Dict[str, Any] | None = None
    semantic_representation: SemanticRepresentation | None = None
    semantic_projection: SemanticProjection | None = None
    semantic_authority_pilot: Dict[str, Any] = field(default_factory=dict)
    conversational_goal_authority: Dict[str, Any] = field(default_factory=dict)


class ConversationManager:
    """Owns conversation lifecycle.

    The Conversation Manager does not interpret insurance content.
    It tracks session continuity and provides the active CSM to the runtime.
    """

    def __init__(
        self,
        semantic_authority: SemanticAuthority | None = None,
        semantic_projector: SemanticProjector | None = None,
        semantic_authority_pilot_enabled: bool | None = None,
    ) -> None:
        self._sessions: Dict[str, ConversationSession] = {}
        self.semantic_authority = semantic_authority or SemanticAuthority()
        self.semantic_projector = semantic_projector or SemanticProjector()
        self.semantic_authority_pilot_enabled = (
            semantic_authority_pilot_enabled
            if semantic_authority_pilot_enabled is not None
            else semantic_authority_pilot_enabled_from_env()
        )

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
        legacy_state, legacy_conversational_act = initial.recognize_conversational_act(
            event.payload
        )
        session.last_legacy_conversational_act = dict(legacy_conversational_act)
        semantic_representation = None
        semantic_projection = None
        semantic_failure = None
        try:
            semantic_representation = self.semantic_authority.interpret(
                event,
                conversation_state=initial,
                turn_number=len(session.turns),
            )
            session.last_semantic_representation = semantic_representation
            session.semantic_representation_count += 1
            semantic_projection = self.semantic_projector.project(semantic_representation)
            session.last_semantic_projection = semantic_projection
            session.semantic_projection_count += 1
            session.last_semantic_failure = None
        except Exception as exc:
            semantic_failure = {
                "type": type(exc).__name__,
                "message": str(exc),
                "turn": len(session.turns),
            }
            session.last_semantic_representation = None
            session.last_semantic_projection = None
            session.last_semantic_failure = dict(semantic_failure)
        initial = legacy_state
        semantic_authority_pilot = select_conversational_act_authority(
            legacy_act=legacy_conversational_act,
            semantic_projection=semantic_projection,
            semantic_representation=semantic_representation,
            enabled=self.semantic_authority_pilot_enabled,
            semantic_failure=semantic_failure,
        )
        conversational_act = dict(semantic_authority_pilot["selected_value"])
        derived_state = dict(initial.derived_state)
        derived_state["conversation_act"] = conversational_act_trace(
            semantic_authority_pilot
        )
        projection_sources = initial.projection_sources
        if semantic_authority_pilot["authority_selected"] == "semantic":
            projection_sources = tuple(
                source
                for source in projection_sources
                if source != "conversation_state.conversational_act_recognition"
            )
            projection_sources = _append_unique(
                projection_sources,
                "semantic_authority.conversational_act",
            )
        initial = replace(
            initial,
            last_conversational_act=conversational_act,
            derived_state=derived_state,
            projection_sources=projection_sources,
        )
        session.last_semantic_authority_pilot = dict(semantic_authority_pilot)
        session.semantic_authority_pilot_history.append(dict(semantic_authority_pilot))
        resolved, slot_resolutions = initial.resolve_pending_slot_answers(event.payload)
        initial = resolved
        initial, fact_assimilations, mission_advancement = initial.assimilate_user_facts(event.payload)
        initial, topic_transition = initial.update_topic_stack(event.payload)
        semantic_projection_data = (
            semantic_projection.to_dict() if semantic_projection is not None else {}
        )
        semantic_goal_projection = dict(
            semantic_projection_data.get("goal_projection") or {}
        )
        projection_metadata = {
            "projection_id": semantic_projection_data.get("projection_id"),
            "representation_id": semantic_projection_data.get("representation_id"),
        }
        legacy_goal = initial.project_conversational_goal(
            source="conversation_state.structured_legacy_goal",
        )
        semantic_goal = initial.project_conversational_goal(
            source="semantic_projection.goal_projection",
            goal_projection=semantic_goal_projection,
            projection_metadata=projection_metadata,
        )
        legacy_goal_state, _ = initial.apply_conversational_goal(legacy_goal)
        semantic_goal_state, _ = initial.apply_conversational_goal(semantic_goal)
        conversational_goal_authority = select_conversational_goal_authority(
            legacy_goal=legacy_goal,
            semantic_goal=semantic_goal,
            legacy_state_effect=conversational_goal_state_effect(legacy_goal_state),
            semantic_state_effect=conversational_goal_state_effect(semantic_goal_state),
            semantic_projection=semantic_projection_data or None,
            enabled=self.semantic_authority_pilot_enabled,
            semantic_failure=semantic_failure,
        )
        initial, conversational_goal = initial.apply_conversational_goal(
            conversational_goal_authority["selected_value"],
            authority_decision=conversational_goal_authority,
        )
        session.last_conversational_goal_authority = dict(
            conversational_goal_authority
        )
        session.conversational_goal_authority_history.append(
            dict(conversational_goal_authority)
        )
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
        if semantic_representation is not None:
            session.last_projection_log.append(
                {
                    "component": "semantic_authority",
                    "direction": "UserMessage -> SemanticRepresentation",
                    "reason": "sa_1_shadow_semantic_representation",
                    "authority_mode": "legacy",
                    "semantic_authority_mode": "shadow",
                    "semantic_representation_id": semantic_representation.representation_id,
                    "semantic_version": semantic_representation.version,
                    "semantic_projection_hash": semantic_representation.projection_hash,
                    "decision_influence": False,
                    "state_mutation": False,
                }
            )
        if semantic_projection is not None:
            session.last_projection_log.append(
                {
                    "component": "semantic_projector",
                    "direction": "SemanticRepresentation -> SemanticProjection",
                    "reason": "sa_2_shadow_semantic_projection",
                    "authority_mode": "legacy",
                    "semantic_authority_mode": "shadow",
                    "semantic_projection_id": semantic_projection.projection_id,
                    "semantic_projection_version": semantic_projection.version,
                    "semantic_projection_hash": semantic_projection.projection_hash,
                    "decision_influence": False,
                    "state_mutation": False,
                }
            )
        session.last_projection_log.append(
            {
                "component": "semantic_authority",
                "direction": "SemanticProjection -> ConversationalAct",
                "reason": "sa_3_vertical_authority_selection",
                "consumer": "conversational_act",
                "authority_mode": semantic_authority_pilot["authority_mode"],
                "authority_reason": semantic_authority_pilot["authority_reason"],
                "authority_selected": semantic_authority_pilot["authority_selected"],
                "confidence": semantic_authority_pilot["confidence"],
                "rollback_reason": semantic_authority_pilot["rollback_reason"],
                "firewall_package": semantic_authority_pilot["firewall_package"],
                "legacy_capture_phase": semantic_authority_pilot[
                    "legacy_capture_phase"
                ],
                "downstream_text_access": semantic_authority_pilot[
                    "downstream_text_access"
                ],
                "atomic_selection": True,
                "mixed_authority": False,
            }
        )
        session.last_projection_log.append(
            {
                "component": "conversation_state",
                "direction": "SemanticProjection -> ConversationalGoal",
                "reason": "fw_5_conversational_goal_authority_selection",
                "consumer": "conversational_goal",
                "authority_mode": conversational_goal_authority["authority_mode"],
                "authority_reason": conversational_goal_authority["authority_reason"],
                "authority_selected": conversational_goal_authority[
                    "authority_selected"
                ],
                "confidence": conversational_goal_authority["confidence"],
                "rollback_reason": conversational_goal_authority["rollback_reason"],
                "agreement": conversational_goal_authority["agreement"],
                "state_delta_parity": conversational_goal_authority[
                    "state_delta_parity"
                ],
                "firewall_package": conversational_goal_authority[
                    "firewall_package"
                ],
                "downstream_text_access": False,
                "atomic_selection": True,
                "mixed_authority": False,
            }
        )
        if conversational_act:
            session.last_projection_log.append(
                {
                    "component": (
                        "semantic_projector"
                        if semantic_authority_pilot["authority_selected"] == "semantic"
                        else "conversation_state"
                    ),
                    "direction": "SelectedAuthority -> ConversationalAct",
                    "reason": "conversational_act_authority_applied",
                    "authority_mode": semantic_authority_pilot["authority_mode"],
                    "authority_selected": semantic_authority_pilot["authority_selected"],
                    "act": conversational_act.get("act"),
                    "confidence": conversational_act.get("confidence"),
                }
            )
        if conversational_goal:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "ConversationalAct -> ConversationalGoal",
                    "reason": "conversational_goal",
                    "act": conversational_goal.get("act"),
                    "strategy": (conversational_goal.get("strategy") or {}).get("name"),
                    "priority": conversational_goal.get("priority"),
                }
            )
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
        if topic_transition:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "UserMessage -> TopicStack",
                    "reason": "topic_stack_transition",
                    "transition": (topic_transition.get("transition") or {}).get("type"),
                    "active_topic_id": (topic_transition.get("active_topic") or {}).get("id"),
                    "suspended_topic_id": (topic_transition.get("topic_suspended") or {}).get("id"),
                    "resumed_topic_id": (topic_transition.get("topic_resumed") or {}).get("id"),
                }
            )
        return ConversationTurnContext(
            conversation_id=conversation_id,
            conversation_state=initial,
            cognitive_state=cognitive_state,
            projections=projections,
            conversational_act=dict(conversational_act),
            conversational_goal=dict(conversational_goal),
            slot_resolutions=tuple(dict(resolution) for resolution in slot_resolutions),
            fact_assimilations=tuple(dict(item) for item in fact_assimilations),
            fact_revisions=tuple(dict(item) for item in fact_revisions),
            mission_advancement=dict(mission_advancement) if mission_advancement else None,
            topic_transition=dict(topic_transition) if topic_transition else None,
            semantic_representation=semantic_representation,
            semantic_projection=semantic_projection,
            semantic_authority_pilot=dict(semantic_authority_pilot),
            conversational_goal_authority=dict(conversational_goal_authority),
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
        final_state, fulfillment = final_state.evaluate_conversational_goal_fulfillment(state.response)
        if fulfillment:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "Response -> ConversationalGoal",
                    "reason": "conversational_goal_fulfillment",
                    "strategy": fulfillment.get("strategy"),
                    "status": fulfillment.get("status"),
                    "satisfied": fulfillment.get("satisfied"),
                }
            )
        final_state, conversation_fulfillment = final_state.evaluate_conversation_fulfillment(state.response)
        if conversation_fulfillment:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "Response -> ConversationFulfillment",
                    "reason": "conversation_plan_fulfillment",
                    "status": (conversation_fulfillment.get("fulfilled_goal") or {}).get("status"),
                    "fulfilled_step_count": len(conversation_fulfillment.get("fulfilled_steps") or []),
                    "pending_step_count": len(conversation_fulfillment.get("pending_steps") or []),
                    "failed_step_count": len(conversation_fulfillment.get("failed_steps") or []),
                    "recovery_actions": [
                        action.get("action")
                        for action in conversation_fulfillment.get("recovery_actions") or []
                    ],
                    "fulfillment_confidence": conversation_fulfillment.get("fulfillment_confidence"),
                }
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

    def record_conversation_planning_projection(
        self,
        conversation_id: str,
        *,
        conversational_intent_model: Dict[str, Any],
        information_gain_plan: Dict[str, Any],
        conversation_plan: Dict[str, Any],
        conversational_response_plan: Dict[str, Any],
    ) -> None:
        """Append the turn's planning projection-log entries.

        ConversationIntentModel, InformationGainPlan, ConversationPlan and
        ConversationResponsePlan are computed exactly once per turn, in
        ACAOSRuntime.process after MissionManager runs (see FW-11). This
        records the same audit-trail entries begin_turn used to record when
        it still computed these artifacts itself, sourced from the single
        authoritative computation instead.
        """
        session = self.open(conversation_id)
        if conversational_intent_model:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "UserMessage -> ConversationalIntentModel",
                    "reason": "conversational_intent_decomposition",
                    "dominant_concern": (
                        conversational_intent_model.get("dominant_concern") or {}
                    ).get("key"),
                    "response_objective": (
                        conversational_intent_model.get("response_objective") or {}
                    ).get("key"),
                    "implicit_question_count": len(
                        conversational_intent_model.get("implicit_questions") or []
                    ),
                }
            )
        if information_gain_plan:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "ConversationalIntentModel -> InformationGainPlan",
                    "reason": "information_gain_planning",
                    "candidate_question_count": len(
                        information_gain_plan.get("candidate_questions") or []
                    ),
                    "selected_slot": (
                        information_gain_plan.get("selected_question") or {}
                    ).get("slot"),
                    "selection_reason": information_gain_plan.get("selection_reason"),
                    "avoided_question_count": (
                        information_gain_plan.get("question_count_metric") or {}
                    ).get("avoided_question_count"),
                }
            )
        if conversation_plan:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "InformationGainPlan -> ConversationPlan",
                    "reason": "dynamic_conversation_planning",
                    "replanning_reason": conversation_plan.get("replanning_reason"),
                    "completed_step_count": len(conversation_plan.get("completed_steps") or []),
                    "pending_step_count": len(conversation_plan.get("pending_steps") or []),
                    "inserted_step_count": len(conversation_plan.get("inserted_steps") or []),
                    "skipped_step_count": len(conversation_plan.get("skipped_steps") or []),
                    "conversation_progress": conversation_plan.get("conversation_progress"),
                }
            )
        if conversational_response_plan:
            session.last_projection_log.append(
                {
                    "component": "conversation_state",
                    "direction": "ConversationalState -> ConversationalResponsePlan",
                    "reason": "conversation_response_planning",
                    "primary_user_need": (
                        conversational_response_plan.get("primary_user_need") or {}
                    ).get("key"),
                    "dominant_concern": (
                        conversational_response_plan.get("dominant_concern") or {}
                    ).get("key"),
                    "response_priority": list(
                        conversational_response_plan.get("response_priority") or []
                    ),
                }
            )

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
        semantic_shadow = semantic_shadow_record(session.last_semantic_representation)
        derived = (final.derived_state or {}) if final else {}
        active_state = session.active_state
        topic_projection_source = derived.get("topic_stack", {})
        if not topic_projection_source and final:
            topic_projection_source = {
                "topics": [dict(topic) for topic in final.topic_stack],
                "active_topic": next(
                    (
                        dict(topic)
                        for topic in final.topic_stack
                        if topic.get("status") in {"active", "resumed"}
                    ),
                    {},
                ),
            }
        legacy_semantic_projection = capture_legacy_projection(
            conversational_act=session.last_legacy_conversational_act,
            conversation_intent_model=derived.get("conversation_intent_model", {}),
            intent_match=(active_state.intent_match if active_state else {}),
            entities=(active_state.entities if active_state else {}),
            fact_assimilation=derived.get("fact_assimilation", {}),
            fact_revision=derived.get("fact_revision", {}),
            slot_resolution=derived.get("slot_resolution", {}),
            slots=(final.slots if final else {}),
            topic_stack=topic_projection_source,
            conversation_goal=derived.get("conversation_goal", {}),
        )
        semantic_projection_comparison = (
            compare_semantic_projection(
                legacy_semantic_projection,
                session.last_semantic_projection,
            )
            if session.last_semantic_projection is not None
            else {}
        )
        semantic_projection_shadow = semantic_projection_shadow_record(
            session.last_semantic_projection,
            semantic_projection_comparison,
        )
        return {
            "contract": "conversation_state_runtime.v1",
            "available": final is not None,
            "operational_owner": "conversation_manager",
            "conversation_id": conversation_id,
            "turn_count": len(session.turns),
            "initial_state": initial.to_dict() if initial else {},
            "final_state": final.to_dict() if final else {},
            "changes": [dict(change) for change in session.last_state_changes],
            "conversation_act": (final.derived_state or {}).get("conversation_act", {}) if final else {},
            "conversation_goal": (final.derived_state or {}).get("conversation_goal", {}) if final else {},
            "conversation_intent_model": (final.derived_state or {}).get("conversation_intent_model", {}) if final else {},
            "conversation_information_gain_plan": (final.derived_state or {}).get("conversation_information_gain_plan", {}) if final else {},
            "conversation_plan": (final.derived_state or {}).get("conversation_plan", {}) if final else {},
            "conversation_response_plan": (final.derived_state or {}).get("conversation_response_plan", {}) if final else {},
            "conversation_fulfillment": (final.derived_state or {}).get("conversation_fulfillment", {}) if final else {},
            "topic_stack": (final.derived_state or {}).get("topic_stack", {}) if final else {},
            "active_topic": (
                ((final.derived_state or {}).get("topic_stack", {}) or {}).get("active_topic")
                if final
                else {}
            ),
            "fact_assimilation": (final.derived_state or {}).get("fact_assimilation", {}) if final else {},
            "fact_revision": (final.derived_state or {}).get("fact_revision", {}) if final else {},
            "mission_advancement": (final.derived_state or {}).get("mission_advancement", {}) if final else {},
            "semantic_shadow": semantic_shadow,
            "semantic_representation_count": session.semantic_representation_count,
            "semantic_projection_shadow": semantic_projection_shadow,
            "semantic_projection_count": session.semantic_projection_count,
            "semantic_authority_pilot": dict(
                session.last_semantic_authority_pilot
            ),
            "semantic_authority_pilot_metrics": summarize_semantic_authority_pilot(
                session.semantic_authority_pilot_history
            ),
            "conversational_goal_authority": dict(
                session.last_conversational_goal_authority
            ),
            "conversational_goal_authority_metrics": summarize_conversational_goal_authority(
                session.conversational_goal_authority_history
            ),
            "semantic_failure": dict(session.last_semantic_failure or {}),
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
            topic_stack=projection.topic_stack if has_operational_topic_stack(projection.topic_stack) else previous.topic_stack,
            focus=projection.focus if has_operational_topic_stack(projection.topic_stack) else previous.focus or projection.focus,
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


def has_operational_topic_stack(values: list[Dict[str, Any]]) -> bool:
    return any(
        isinstance(topic, dict) and topic.get("contract") == "conversation_topic.v1"
        for topic in values or []
    )


def deep_merge(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(left or {})
    merged.update(dict(right or {}))
    return merged


TURN_SCOPED_DERIVED_STATE_KEYS = {
    "conversation_act",
    "conversation_goal",
    "conversation_intent_model",
    "conversation_information_gain_plan",
    "conversation_response_plan",
    "conversation_fulfillment",
    "slot_resolution",
    "fact_assimilation",
    "fact_revision",
    "mission_advancement",
    "topic_stack",
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
