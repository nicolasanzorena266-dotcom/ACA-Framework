from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, fields, replace
from typing import Any, Dict, Mapping, Sequence

from aca_core.text import normalize_text
from aca_kernel.core.state import CognitiveState


class ConversationStateCategory:
    CENTRAL = "central"
    DERIVED = "derived"
    PRODUCT = "product"
    TEMPORARY = "temporary"
    PERSISTENT = "persistent"


VALID_CONVERSATION_STATE_CATEGORIES = {
    ConversationStateCategory.CENTRAL,
    ConversationStateCategory.DERIVED,
    ConversationStateCategory.PRODUCT,
    ConversationStateCategory.TEMPORARY,
    ConversationStateCategory.PERSISTENT,
}


class SlotStatus:
    PENDING = "pending"
    PARTIALLY_FILLED = "partially_filled"
    ANSWERED = "answered"
    CONFIRMED = "confirmed"
    INVALIDATED = "invalidated"
    REFUTED = "refuted"


VALID_SLOT_STATUSES = {
    SlotStatus.PENDING,
    SlotStatus.PARTIALLY_FILLED,
    SlotStatus.ANSWERED,
    SlotStatus.CONFIRMED,
    SlotStatus.INVALIDATED,
    SlotStatus.REFUTED,
}


SLOT_LIFECYCLE = {
    SlotStatus.PENDING: (SlotStatus.PARTIALLY_FILLED, SlotStatus.ANSWERED, SlotStatus.INVALIDATED),
    SlotStatus.PARTIALLY_FILLED: (SlotStatus.ANSWERED, SlotStatus.INVALIDATED, SlotStatus.REFUTED),
    SlotStatus.ANSWERED: (SlotStatus.CONFIRMED, SlotStatus.REFUTED, SlotStatus.INVALIDATED),
    SlotStatus.CONFIRMED: (SlotStatus.REFUTED, SlotStatus.INVALIDATED),
    SlotStatus.INVALIDATED: (SlotStatus.PENDING,),
    SlotStatus.REFUTED: (SlotStatus.PENDING,),
}


SLOT_CLOSED_STATUSES = {
    SlotStatus.ANSWERED,
    SlotStatus.CONFIRMED,
    SlotStatus.INVALIDATED,
    SlotStatus.REFUTED,
}


class MissionLifecycleStatus:
    INITIALIZED = "initialized"
    GATHERING_INFORMATION = "gathering_information"
    READY_TO_PROGRESS = "ready_to_progress"
    PROGRESSING = "progressing"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    SUSPENDED = "suspended"


VALID_MISSION_LIFECYCLE_STATUSES = {
    MissionLifecycleStatus.INITIALIZED,
    MissionLifecycleStatus.GATHERING_INFORMATION,
    MissionLifecycleStatus.READY_TO_PROGRESS,
    MissionLifecycleStatus.PROGRESSING,
    MissionLifecycleStatus.WAITING_USER,
    MissionLifecycleStatus.COMPLETED,
    MissionLifecycleStatus.SUSPENDED,
}


MISSION_LIFECYCLE = {
    MissionLifecycleStatus.INITIALIZED: (
        MissionLifecycleStatus.GATHERING_INFORMATION,
        MissionLifecycleStatus.WAITING_USER,
        MissionLifecycleStatus.READY_TO_PROGRESS,
        MissionLifecycleStatus.SUSPENDED,
    ),
    MissionLifecycleStatus.GATHERING_INFORMATION: (
        MissionLifecycleStatus.WAITING_USER,
        MissionLifecycleStatus.READY_TO_PROGRESS,
        MissionLifecycleStatus.PROGRESSING,
        MissionLifecycleStatus.SUSPENDED,
    ),
    MissionLifecycleStatus.READY_TO_PROGRESS: (
        MissionLifecycleStatus.PROGRESSING,
        MissionLifecycleStatus.WAITING_USER,
        MissionLifecycleStatus.COMPLETED,
        MissionLifecycleStatus.SUSPENDED,
    ),
    MissionLifecycleStatus.PROGRESSING: (
        MissionLifecycleStatus.WAITING_USER,
        MissionLifecycleStatus.READY_TO_PROGRESS,
        MissionLifecycleStatus.COMPLETED,
        MissionLifecycleStatus.SUSPENDED,
    ),
    MissionLifecycleStatus.WAITING_USER: (
        MissionLifecycleStatus.GATHERING_INFORMATION,
        MissionLifecycleStatus.READY_TO_PROGRESS,
        MissionLifecycleStatus.PROGRESSING,
        MissionLifecycleStatus.SUSPENDED,
    ),
    MissionLifecycleStatus.COMPLETED: (MissionLifecycleStatus.SUSPENDED,),
    MissionLifecycleStatus.SUSPENDED: (
        MissionLifecycleStatus.GATHERING_INFORMATION,
        MissionLifecycleStatus.WAITING_USER,
    ),
}


class FactStatus:
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    REFUTED = "refuted"
    WITHDRAWN = "withdrawn"
    OBSOLETE = "obsolete"


VALID_FACT_STATUSES = {
    FactStatus.ACTIVE,
    FactStatus.SUPERSEDED,
    FactStatus.REFUTED,
    FactStatus.WITHDRAWN,
    FactStatus.OBSOLETE,
}


FACT_LIFECYCLE = {
    FactStatus.ACTIVE: (
        FactStatus.SUPERSEDED,
        FactStatus.REFUTED,
        FactStatus.WITHDRAWN,
        FactStatus.OBSOLETE,
    ),
    FactStatus.SUPERSEDED: (FactStatus.OBSOLETE,),
    FactStatus.REFUTED: (FactStatus.OBSOLETE,),
    FactStatus.WITHDRAWN: (FactStatus.OBSOLETE,),
    FactStatus.OBSOLETE: (),
}


class ConversationalActType:
    PENDING_ANSWER = "pending_answer"
    CONFIRMATION = "confirmation"
    NEGATION = "negation"
    CORRECTION = "correction"
    CLARIFICATION = "clarification"
    CLARIFICATION_REQUEST = "clarification_request"
    TOPIC_SHIFT = "topic_shift"
    CONTINUATION = "continuation"
    RECAP_REQUEST = "recap_request"
    SIMPLIFICATION_REQUEST = "simplification_request"
    DEEPENING_REQUEST = "deepening_request"
    CLOSING = "closing"
    NEW_INFORMATION = "new_information"
    UNKNOWN = "unknown"


VALID_CONVERSATIONAL_ACT_TYPES = {
    ConversationalActType.PENDING_ANSWER,
    ConversationalActType.CONFIRMATION,
    ConversationalActType.NEGATION,
    ConversationalActType.CORRECTION,
    ConversationalActType.CLARIFICATION,
    ConversationalActType.CLARIFICATION_REQUEST,
    ConversationalActType.TOPIC_SHIFT,
    ConversationalActType.CONTINUATION,
    ConversationalActType.RECAP_REQUEST,
    ConversationalActType.SIMPLIFICATION_REQUEST,
    ConversationalActType.DEEPENING_REQUEST,
    ConversationalActType.CLOSING,
    ConversationalActType.NEW_INFORMATION,
    ConversationalActType.UNKNOWN,
}


class ConversationalStrategyType:
    RESPOND = "respond"
    SIMPLIFY = "simplify"
    DEEPEN = "deepen"
    SUMMARIZE = "summarize"
    CONTINUE = "continue"
    REPAIR = "repair"
    SWITCH_TOPIC = "switch_topic"
    CLOSE = "close"
    ASK_CLARIFICATION = "ask_clarification"


VALID_CONVERSATIONAL_STRATEGIES = {
    ConversationalStrategyType.RESPOND,
    ConversationalStrategyType.SIMPLIFY,
    ConversationalStrategyType.DEEPEN,
    ConversationalStrategyType.SUMMARIZE,
    ConversationalStrategyType.CONTINUE,
    ConversationalStrategyType.REPAIR,
    ConversationalStrategyType.SWITCH_TOPIC,
    ConversationalStrategyType.CLOSE,
    ConversationalStrategyType.ASK_CLARIFICATION,
}


class TopicStatus:
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RESUMED = "resumed"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


VALID_TOPIC_STATUSES = {
    TopicStatus.ACTIVE,
    TopicStatus.SUSPENDED,
    TopicStatus.RESUMED,
    TopicStatus.COMPLETED,
    TopicStatus.ABANDONED,
}


TOPIC_ACTIVE_STATUSES = {
    TopicStatus.ACTIVE,
    TopicStatus.RESUMED,
}


TOPIC_LIFECYCLE = {
    TopicStatus.ACTIVE: (TopicStatus.SUSPENDED, TopicStatus.COMPLETED, TopicStatus.ABANDONED),
    TopicStatus.SUSPENDED: (TopicStatus.RESUMED, TopicStatus.ABANDONED),
    TopicStatus.RESUMED: (TopicStatus.ACTIVE, TopicStatus.SUSPENDED, TopicStatus.COMPLETED, TopicStatus.ABANDONED),
    TopicStatus.COMPLETED: (),
    TopicStatus.ABANDONED: (),
}


@dataclass(frozen=True)
class ConversationFieldOwnership:
    field: str
    category: str
    owner: str
    lifecycle: str
    writers: tuple[str, ...]
    readers: tuple[str, ...]
    projection_sources: tuple[str, ...] = ()
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "category": self.category,
            "owner": self.owner,
            "lifecycle": self.lifecycle,
            "writers": list(self.writers),
            "readers": list(self.readers),
            "projection_sources": list(self.projection_sources),
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class ConversationState:
    """Canonical conversation-state contract.

    This is a projection contract. It does not execute policy, route flows or
    mutate current runtime behavior. Existing runtime and public-demo structures
    can project into this shape while ownership is consolidated.
    """

    contract: str = "conversation_state.v1"
    conversation_id: str = "default"
    turn_count: int = 0
    focus: Dict[str, Any] = field(default_factory=dict)
    topic_stack: list[Dict[str, Any]] = field(default_factory=list)
    active_mission: Dict[str, Any] | None = None
    goals: list[Dict[str, Any]] = field(default_factory=list)
    slots: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    confirmed_facts: Dict[str, Any] = field(default_factory=dict)
    refuted_facts: Dict[str, Any] = field(default_factory=dict)
    active_hypotheses: Dict[str, float] = field(default_factory=dict)
    relevant_evidence: Dict[str, Any] = field(default_factory=dict)
    conversational_strategy: Dict[str, Any] = field(default_factory=dict)
    pending_questions: list[Dict[str, Any]] = field(default_factory=list)
    last_conversational_act: Dict[str, Any] = field(default_factory=dict)
    conversation_summary: str | None = None
    user_signals: Dict[str, Any] = field(default_factory=dict)
    relevant_context: Dict[str, Any] = field(default_factory=dict)
    product_state: Dict[str, Any] = field(default_factory=dict)
    derived_state: Dict[str, Any] = field(default_factory=dict)
    temporary_state: Dict[str, Any] = field(default_factory=dict)
    projection_sources: tuple[str, ...] = ()

    @classmethod
    def from_cognitive_state(
        cls,
        state: Any,
        *,
        turn_count: int = 0,
        source: str = "cognitive_state",
    ) -> "ConversationState":
        active_mission = _mapping_or_none(getattr(state, "active_mission", None))
        focus = _focus_from_cognitive_state(state, active_mission)
        topic_stack = _topic_stack_from_cognitive_facts(
            dict(getattr(state, "facts", {}) or {}),
            focus=focus,
            active_mission=active_mission,
            turn_count=turn_count,
        )
        slots = _slots_from_mission(active_mission, source="active_mission")
        pending_questions = _pending_questions_from_slots(slots, source="active_mission")
        facts = _conversation_facts_from_cognitive_state(state)
        goals = _goals_from_cognitive_state(state, active_mission)
        last_act = _last_act_from_cognitive_state(state)
        context_bundle = _mapping_or_none(getattr(state, "context_bundle", None))
        derived_state = _derived_state_from_cognitive_state(state, context_bundle)
        relevant_context = _relevant_context_from_context_bundle(context_bundle)

        return cls(
            conversation_id=str(getattr(state, "conversation_id", "default")),
            turn_count=turn_count,
            focus=focus,
            topic_stack=topic_stack,
            active_mission=active_mission,
            goals=goals,
            slots=slots,
            confirmed_facts=facts,
            refuted_facts={},
            active_hypotheses=dict(getattr(state, "hypotheses", {}) or {}),
            relevant_evidence=dict(getattr(state, "tool_evidence", {}) or {}),
            conversational_strategy={},
            pending_questions=pending_questions,
            last_conversational_act=last_act,
            conversation_summary=None,
            user_signals={},
            relevant_context=relevant_context,
            product_state={},
            derived_state=derived_state,
            temporary_state={},
            projection_sources=(source,),
        )

    @classmethod
    def from_public_state(
        cls,
        state: Any,
        *,
        semantic_parse: Mapping[str, Any] | None = None,
        planner_decision: Mapping[str, Any] | None = None,
        supervisor_result: Mapping[str, Any] | None = None,
        context_bundle: Mapping[str, Any] | None = None,
        source: str = "public_conversation_state",
    ) -> "ConversationState":
        semantic = dict(semantic_parse or {})
        planner = dict(planner_decision or {})
        supervisor = dict(supervisor_result or {})
        context = dict(context_bundle or {})
        confirmed_facts = _facts_from_sequence(getattr(state, "known_facts", ()) or ())
        confirmed_facts.update(_facts_from_sequence(semantic.get("known_facts") or ()))
        slots = _slots_from_missing(getattr(state, "missing_facts", ()) or (), source="public_conversation_state")
        slots.update(_slots_from_missing(semantic.get("missing_facts") or (), source="semantic_parse"))
        focus = _focus_from_public_state(state, semantic)
        goals = _goals_from_public_state(state, semantic)
        signals = dict(getattr(state, "interaction_signals", None) or {})
        signals.update(dict(semantic.get("signals") or {}))

        return cls(
            conversation_id=str(getattr(state, "conversation_id", "public")),
            turn_count=int(getattr(state, "turn_count", 0) or 0),
            focus=focus,
            topic_stack=_topic_stack_from_focus(focus),
            active_mission=None,
            goals=goals,
            slots=slots,
            confirmed_facts=confirmed_facts,
            refuted_facts={},
            active_hypotheses={},
            relevant_evidence={},
            conversational_strategy=_strategy_from_planner(planner, getattr(state, "next_action_suggested", None)),
            pending_questions=_pending_questions_from_slots(slots, source="public_conversation_state"),
            last_conversational_act=_last_act_from_public_state(state, semantic),
            conversation_summary=None,
            user_signals=signals,
            relevant_context=_relevant_context_from_context_bundle(context),
            product_state=_product_state_from_public_state(state),
            derived_state=_derived_state_from_public_projection(semantic, planner, supervisor, context),
            temporary_state={},
            projection_sources=tuple(
                source_name
                for source_name, present in (
                    (source, True),
                    ("semantic_parse", bool(semantic)),
                    ("planner_decision", bool(planner)),
                    ("supervisor_result", bool(supervisor)),
                    ("context_bundle", bool(context)),
                )
                if present
            ),
        )

    @classmethod
    def from_context_bundle(
        cls,
        context_bundle: Mapping[str, Any],
        *,
        conversation_id: str = "derived-context",
        turn_count: int = 0,
    ) -> "ConversationState":
        context = dict(context_bundle)
        mission = _mapping_or_none(context.get("mission"))
        focus = _focus_from_context_bundle(context, mission)
        slots = _slots_from_mission(mission, source="context_bundle.mission")
        return cls(
            conversation_id=conversation_id,
            turn_count=turn_count,
            focus=focus,
            topic_stack=_topic_stack_from_focus(focus),
            active_mission=mission,
            goals=_goals_from_mission(mission),
            slots=slots,
            confirmed_facts=dict(context.get("facts") or {}),
            active_hypotheses=dict(context.get("hypotheses") or {}),
            relevant_evidence=dict(context.get("tool_evidence") or {}),
            pending_questions=_pending_questions_from_slots(slots, source="context_bundle"),
            relevant_context=_relevant_context_from_context_bundle(context),
            derived_state={"context_bundle": deepcopy(context)},
            projection_sources=("context_bundle",),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "conversation_id": self.conversation_id,
            "turn_count": self.turn_count,
            "focus": deepcopy(self.focus),
            "topic_stack": deepcopy(self.topic_stack),
            "active_mission": deepcopy(self.active_mission),
            "goals": deepcopy(self.goals),
            "slots": deepcopy(self.slots),
            "confirmed_facts": deepcopy(self.confirmed_facts),
            "refuted_facts": deepcopy(self.refuted_facts),
            "active_hypotheses": deepcopy(self.active_hypotheses),
            "relevant_evidence": deepcopy(self.relevant_evidence),
            "conversational_strategy": deepcopy(self.conversational_strategy),
            "pending_questions": deepcopy(self.pending_questions),
            "last_conversational_act": deepcopy(self.last_conversational_act),
            "conversation_summary": self.conversation_summary,
            "user_signals": deepcopy(self.user_signals),
            "relevant_context": deepcopy(self.relevant_context),
            "product_state": deepcopy(self.product_state),
            "derived_state": deepcopy(self.derived_state),
            "temporary_state": deepcopy(self.temporary_state),
            "projection_sources": list(self.projection_sources),
        }

    def to_cognitive_state(
        self,
        *,
        base: CognitiveState | None = None,
        source: str = "conversation_state",
    ) -> CognitiveState:
        """Project the canonical conversation state into the legacy runtime carrier."""

        data = base.to_dict() if base is not None else CognitiveState(conversation_id=self.conversation_id).to_dict()
        facts = dict(data.get("facts") or {})
        for key in self.refuted_facts:
            if key not in self.confirmed_facts:
                facts.pop(str(key), None)
                facts.pop(f"fact.{key}", None)
        for key, value in self.confirmed_facts.items():
            if isinstance(value, Mapping) and value.get("contract") == "conversational_fact.v1":
                facts[key] = deepcopy(value.get("value"))
                facts[f"fact.{key}"] = deepcopy(dict(value))
            else:
                facts[key] = deepcopy(value)

        derived = dict(self.derived_state or {})
        for key in (
            "zero_cost_action_plan",
            "zero_cost_execution_flow",
            "zero_cost_execution_plan",
            "zero_cost_decision_graph",
            "runtime_execution_engine",
            "conversation_act_recognition",
            "conversation_goal",
            "conversation_intent_model",
            "conversation_information_gain_plan",
            "conversation_plan",
            "conversation_response_plan",
            "conversation_fulfillment",
            "conversation_topic_stack",
            "conversation_slot_resolution",
            "conversation_fact_assimilation",
            "conversation_fact_revision",
            "conversation_mission_advancement",
        ):
            if key in derived and key not in facts:
                facts[key] = deepcopy(derived[key])
        active_topic = _active_topic_from_stack(self.topic_stack)
        if self.topic_stack:
            facts["conversation_topic_stack"] = {
                "contract": "topic_stack_projection.v1",
                "component": "conversation_state",
                "topics": deepcopy(self.topic_stack),
                "active_topic": deepcopy(active_topic or {}),
            }
            if active_topic:
                facts["conversation_active_topic"] = deepcopy(active_topic)
        if self.last_conversational_act:
            facts["conversation_act"] = deepcopy(self.last_conversational_act)
        if "conversation_act" in derived:
            facts["conversation_act_recognition"] = deepcopy(derived["conversation_act"])
        if "conversation_goal" in derived:
            facts["conversation_goal"] = deepcopy(derived["conversation_goal"])
        if "conversation_intent_model" in derived:
            facts["conversation_intent_model"] = deepcopy(derived["conversation_intent_model"])
        if "conversation_information_gain_plan" in derived:
            facts["conversation_information_gain_plan"] = deepcopy(derived["conversation_information_gain_plan"])
        if "conversation_plan" in derived:
            facts["conversation_plan"] = deepcopy(derived["conversation_plan"])
        if "conversation_response_plan" in derived:
            facts["conversation_response_plan"] = deepcopy(derived["conversation_response_plan"])
        if "conversation_fulfillment" in derived:
            facts["conversation_fulfillment"] = deepcopy(derived["conversation_fulfillment"])
        if "topic_stack" in derived:
            facts["conversation_topic_stack"] = deepcopy(derived["topic_stack"])
            active_topic = _active_topic_from_stack(self.topic_stack)
            if active_topic:
                facts["conversation_active_topic"] = deepcopy(active_topic)
        if "slot_resolution" in derived:
            facts["conversation_slot_resolution"] = deepcopy(derived["slot_resolution"])
        if "fact_assimilation" in derived:
            facts["conversation_fact_assimilation"] = deepcopy(derived["fact_assimilation"])
        if "fact_revision" in derived:
            facts["conversation_fact_revision"] = deepcopy(derived["fact_revision"])
        if "mission_advancement" in derived:
            facts["conversation_mission_advancement"] = deepcopy(derived["mission_advancement"])

        data.update(
            {
                "conversation_id": self.conversation_id,
                "facts": facts,
                "active_mission": deepcopy(self.active_mission),
                "hypotheses": deepcopy(self.active_hypotheses),
                "tool_evidence": deepcopy(self.relevant_evidence),
            }
        )
        if self.relevant_context and data.get("context_bundle") is None:
            data["context_bundle"] = deepcopy(self.relevant_context)

        projected = CognitiveState(**data)
        timeline = list(projected.timeline)
        timeline.append(
            {
                "from_version": projected.version,
                "to_version": projected.version,
                "operation": "CONVERSATION_STATE_PROJECT",
                "changes": {
                    "source": source,
                    "conversation_state_contract": self.contract,
                    "projection": "ConversationState -> CognitiveState",
                },
            }
        )
        return CognitiveState(**{**projected.to_dict(), "timeline": timeline})

    def resolve_pending_slot_answers(self, message: Any) -> tuple["ConversationState", list[Dict[str, Any]]]:
        return resolve_pending_slot_answers(self, message)

    def assimilate_user_facts(self, message: Any) -> tuple["ConversationState", list[Dict[str, Any]], Dict[str, Any] | None]:
        return assimilate_user_facts(self, message)

    def recognize_conversational_act(self, message: Any) -> tuple["ConversationState", Dict[str, Any]]:
        return recognize_conversational_act(self, message)

    def project_conversational_goal(
        self,
        *,
        source: str,
        goal_projection: Mapping[str, Any] | None = None,
        projection_metadata: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return project_conversational_goal(
            self,
            source=source,
            goal_projection=goal_projection,
            projection_metadata=projection_metadata,
        )

    def apply_conversational_goal(
        self,
        goal: Mapping[str, Any],
        *,
        authority_decision: Mapping[str, Any] | None = None,
    ) -> tuple["ConversationState", Dict[str, Any]]:
        return apply_conversational_goal(
            self,
            goal,
            authority_decision=authority_decision,
        )

    def update_topic_stack(self, message: Any) -> tuple["ConversationState", Dict[str, Any]]:
        return update_topic_stack(self, message)

    def plan_conversational_response(self, message: Any) -> tuple["ConversationState", Dict[str, Any]]:
        return plan_conversational_response(self, message)

    def model_conversational_intent(self, message: Any) -> tuple["ConversationState", Dict[str, Any]]:
        return model_conversational_intent(self, message)

    def plan_information_gain(self, message: Any) -> tuple["ConversationState", Dict[str, Any]]:
        return plan_information_gain(self, message)

    def plan_conversation(self, message: Any) -> tuple["ConversationState", Dict[str, Any]]:
        return plan_conversation(self, message)

    def evaluate_conversational_goal_fulfillment(self, response: Any) -> tuple["ConversationState", Dict[str, Any]]:
        return evaluate_conversational_goal_fulfillment(self, response)

    def evaluate_conversation_fulfillment(self, response: Any) -> tuple["ConversationState", Dict[str, Any]]:
        return evaluate_conversation_fulfillment(self, response)


@dataclass(frozen=True)
class ConversationStateMutation:
    field: str
    category: str
    component: str
    before: Any
    after: Any

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field": self.field,
            "category": self.category,
            "component": self.component,
            "before": deepcopy(self.before),
            "after": deepcopy(self.after),
        }


CONVERSATION_STATE_FIELD_OWNERSHIP: Dict[str, ConversationFieldOwnership] = {
    "contract": ConversationFieldOwnership(
        field="contract",
        category=ConversationStateCategory.DERIVED,
        owner="conversation_state_contract",
        lifecycle="schema_version",
        writers=("conversation_state_contract",),
        readers=("runtime", "public_layer", "tests", "introspection"),
        rationale="Identifies the canonical projection contract.",
    ),
    "conversation_id": ConversationFieldOwnership(
        field="conversation_id",
        category=ConversationStateCategory.PERSISTENT,
        owner="conversation_manager",
        lifecycle="conversation",
        writers=("conversation_manager", "public_conversation_state"),
        readers=("runtime", "public_layer", "memory_engine", "introspection"),
        projection_sources=("CognitiveState.conversation_id", "PublicConversationState.conversation_id"),
        rationale="Session identity is the anchor for every projection.",
    ),
    "turn_count": ConversationFieldOwnership(
        field="turn_count",
        category=ConversationStateCategory.PERSISTENT,
        owner="conversation_manager",
        lifecycle="conversation",
        writers=("conversation_manager", "public_conversation_state"),
        readers=("runtime", "public_layer", "strategy"),
        projection_sources=("ConversationSession.turns", "PublicConversationState.turn_count"),
        rationale="Turn count is conversation lifecycle state, not domain state.",
    ),
    "focus": ConversationFieldOwnership(
        field="focus",
        category=ConversationStateCategory.CENTRAL,
        owner="conversation_state",
        lifecycle="until_topic_shift_or_closure",
        writers=("conversation_state", "mission_manager", "public_conversation_state"),
        readers=("intent_matcher", "action_planner", "mission_manager", "response_planner"),
        projection_sources=("CognitiveState.active_mission", "PublicConversationState.active_topic"),
        rationale="Active focus must govern follow-up interpretation.",
    ),
    "topic_stack": ConversationFieldOwnership(
        field="topic_stack",
        category=ConversationStateCategory.CENTRAL,
        owner="conversation_state",
        lifecycle="conversation",
        writers=("conversation_state",),
        readers=("intent_matcher", "response_planner", "summary"),
        projection_sources=("focus",),
        rationale="Allows topic suspension and return without duplicating focus fields.",
    ),
    "active_mission": ConversationFieldOwnership(
        field="active_mission",
        category=ConversationStateCategory.CENTRAL,
        owner="mission_manager",
        lifecycle="mission",
        writers=("mission_manager",),
        readers=("runtime_executor", "memory_engine", "context_manager", "response_planner"),
        projection_sources=("CognitiveState.active_mission", "ContextBundle.mission"),
        rationale="Mission remains the runtime task object but is projected into conversation state.",
    ),
    "goals": ConversationFieldOwnership(
        field="goals",
        category=ConversationStateCategory.CENTRAL,
        owner="conversation_state",
        lifecycle="conversation_or_mission",
        writers=("conversation_state", "mission_manager", "public_conversation_state"),
        readers=("planner", "response_planner", "summary"),
        projection_sources=("CognitiveState.goal", "active_mission.goal", "PublicConversationState.active_goal"),
        rationale="Goals must be explicit enough to drive future strategy.",
    ),
    "slots": ConversationFieldOwnership(
        field="slots",
        category=ConversationStateCategory.CENTRAL,
        owner="conversation_state",
        lifecycle="until_filled_confirmed_or_refuted",
        writers=("conversation_state", "mission_manager", "semantic_understanding"),
        readers=("intent_matcher", "planner", "clarification", "response_planner"),
        projection_sources=("active_mission.missing", "PublicConversationState.missing_facts", "SemanticParse.missing_facts"),
        rationale="Slots are the missing-information contract for multi-turn dialogue.",
    ),
    "confirmed_facts": ConversationFieldOwnership(
        field="confirmed_facts",
        category=ConversationStateCategory.CENTRAL,
        owner="conversation_state",
        lifecycle="conversation_or_persistent_memory",
        writers=("conversation_state", "kernel", "semantic_understanding", "tool_engine"),
        readers=("intent_matcher", "planner", "policy_manager", "response_planner"),
        projection_sources=("CognitiveState.facts", "CognitiveState.entities", "PublicConversationState.known_facts"),
        rationale="Facts need one canonical home before they can govern decisions.",
    ),
    "refuted_facts": ConversationFieldOwnership(
        field="refuted_facts",
        category=ConversationStateCategory.CENTRAL,
        owner="conversation_state",
        lifecycle="conversation_or_until_superseded",
        writers=("conversation_state", "semantic_understanding"),
        readers=("hypothesis_revision", "planner", "response_planner"),
        projection_sources=(),
        rationale="Current structures do not support refutation; the contract reserves ownership.",
    ),
    "active_hypotheses": ConversationFieldOwnership(
        field="active_hypotheses",
        category=ConversationStateCategory.CENTRAL,
        owner="hypothesis_engine",
        lifecycle="until_confirmed_refuted_or_expired",
        writers=("kernel_infer", "future_hypothesis_revision"),
        readers=("planner", "policy_manager", "response_planner"),
        projection_sources=("CognitiveState.hypotheses", "ContextBundle.hypotheses"),
        rationale="Hypotheses are central only when future decisions can revise and consume them.",
    ),
    "relevant_evidence": ConversationFieldOwnership(
        field="relevant_evidence",
        category=ConversationStateCategory.CENTRAL,
        owner="evidence_engine",
        lifecycle="conversation_or_evidence_ttl",
        writers=("tool_engine", "future_evidence_ledger"),
        readers=("policy_manager", "kernel", "response_planner"),
        projection_sources=("CognitiveState.tool_evidence", "ContextBundle.tool_evidence"),
        rationale="Evidence must remain separate from facts until evaluated.",
    ),
    "conversational_strategy": ConversationFieldOwnership(
        field="conversational_strategy",
        category=ConversationStateCategory.CENTRAL,
        owner="conversation_planner",
        lifecycle="turn",
        writers=("conversation_planner", "public_conversation_planner"),
        readers=("response_planner", "supervisor"),
        projection_sources=("PlannerDecision", "PublicConversationState.next_action_suggested"),
        rationale="Strategy should guide the next response but not duplicate final output.",
    ),
    "pending_questions": ConversationFieldOwnership(
        field="pending_questions",
        category=ConversationStateCategory.CENTRAL,
        owner="conversation_state",
        lifecycle="until_answered_or_cancelled",
        writers=("conversation_state", "clarification_planner"),
        readers=("semantic_understanding", "planner", "response_planner"),
        projection_sources=("slots",),
        rationale="Pending questions are the bridge from slots to user-facing dialogue.",
    ),
    "last_conversational_act": ConversationFieldOwnership(
        field="last_conversational_act",
        category=ConversationStateCategory.CENTRAL,
        owner="conversation_state",
        lifecycle="turn",
        writers=("conversation_state", "semantic_understanding", "public_conversation_layer"),
        readers=("semantic_understanding", "strategy", "supervisor"),
        projection_sources=("IntentMatch", "SemanticParse", "PublicConversationState.last_category"),
        rationale="Follow-ups need the previous act, not only raw text.",
    ),
    "conversation_summary": ConversationFieldOwnership(
        field="conversation_summary",
        category=ConversationStateCategory.PERSISTENT,
        owner="conversation_state",
        lifecycle="conversation",
        writers=("future_summary_engine",),
        readers=("intent_matcher", "planner", "response_planner", "handoff"),
        projection_sources=(),
        rationale="Current structures lack a summary; the contract reserves one owner.",
    ),
    "user_signals": ConversationFieldOwnership(
        field="user_signals",
        category=ConversationStateCategory.CENTRAL,
        owner="semantic_understanding",
        lifecycle="turn_or_short_window",
        writers=("semantic_understanding", "public_conversation_state"),
        readers=("strategy", "policy_manager", "response_planner"),
        projection_sources=("SemanticParse.signals", "PublicConversationState.interaction_signals"),
        rationale="Frustration, confusion and urgency should drive strategy centrally.",
    ),
    "relevant_context": ConversationFieldOwnership(
        field="relevant_context",
        category=ConversationStateCategory.DERIVED,
        owner="context_manager",
        lifecycle="turn",
        writers=("context_manager",),
        readers=("kernel", "response_planner", "introspection"),
        projection_sources=("ContextBundle",),
        rationale="Context is a view over central state, memory and evidence.",
    ),
    "product_state": ConversationFieldOwnership(
        field="product_state",
        category=ConversationStateCategory.PRODUCT,
        owner="product_layer",
        lifecycle="product_session",
        writers=("public_conversation_state",),
        readers=("public_layer",),
        projection_sources=("PublicConversationState",),
        rationale="Counters and UI-oriented state remain product-specific.",
    ),
    "derived_state": ConversationFieldOwnership(
        field="derived_state",
        category=ConversationStateCategory.DERIVED,
        owner="projection_layer",
        lifecycle="turn",
        writers=("runtime", "public_layer", "context_manager"),
        readers=("introspection", "tests"),
        projection_sources=("ExecutionPlan", "PolicyResult", "PlannerDecision", "SupervisorResult", "ContextBundle"),
        rationale="Derived projections must not become persistent state.",
    ),
    "temporary_state": ConversationFieldOwnership(
        field="temporary_state",
        category=ConversationStateCategory.TEMPORARY,
        owner="runtime",
        lifecycle="turn",
        writers=("runtime",),
        readers=("runtime_executor",),
        projection_sources=(),
        rationale="Transient execution state is explicitly excluded from persistence.",
    ),
    "projection_sources": ConversationFieldOwnership(
        field="projection_sources",
        category=ConversationStateCategory.DERIVED,
        owner="projection_layer",
        lifecycle="turn",
        writers=("projection_layer",),
        readers=("tests", "introspection"),
        projection_sources=(),
        rationale="Identifies which existing structures produced a projection.",
    ),
}


def ownership_snapshot() -> Dict[str, Dict[str, Any]]:
    return {
        field_name: ownership.to_dict()
        for field_name, ownership in sorted(CONVERSATION_STATE_FIELD_OWNERSHIP.items())
    }


def validate_ownership() -> Dict[str, Any]:
    contract_fields = {field.name for field in fields(ConversationState)}
    ownership_fields = set(CONVERSATION_STATE_FIELD_OWNERSHIP)
    missing = sorted(contract_fields - ownership_fields)
    extra = sorted(ownership_fields - contract_fields)
    invalid_categories = sorted(
        field_name
        for field_name, ownership in CONVERSATION_STATE_FIELD_OWNERSHIP.items()
        if ownership.category not in VALID_CONVERSATION_STATE_CATEGORIES
    )
    missing_owners = sorted(
        field_name
        for field_name, ownership in CONVERSATION_STATE_FIELD_OWNERSHIP.items()
        if not ownership.owner or not ownership.writers
    )
    return {
        "contract": "conversation_state_ownership_validation.v1",
        "valid": not missing and not extra and not invalid_categories and not missing_owners,
        "missing_ownership": missing,
        "extra_ownership": extra,
        "invalid_categories": invalid_categories,
        "missing_owners": missing_owners,
        "field_count": len(contract_fields),
    }


def conversation_state_diff(
    before: ConversationState | None,
    after: ConversationState,
    *,
    component_by_field: Mapping[str, str] | None = None,
) -> list[ConversationStateMutation]:
    if before is None:
        before_data: Dict[str, Any] = {}
    else:
        before_data = before.to_dict()
    after_data = after.to_dict()
    components = dict(component_by_field or {})
    mutations: list[ConversationStateMutation] = []
    for field_name in sorted(after_data):
        if field_name in {"contract", "projection_sources"}:
            continue
        previous = before_data.get(field_name)
        current = after_data.get(field_name)
        if previous == current:
            continue
        ownership = CONVERSATION_STATE_FIELD_OWNERSHIP.get(field_name)
        mutations.append(
            ConversationStateMutation(
                field=field_name,
                category=ownership.category if ownership else "unknown",
                component=components.get(field_name, _default_component_for_field(field_name)),
                before=previous,
                after=current,
            )
        )
    return mutations


def resolve_pending_slot_answers(
    conversation_state: ConversationState,
    message: Any,
) -> tuple[ConversationState, list[Dict[str, Any]]]:
    normalized = normalize_text(message)
    if not normalized:
        return conversation_state, []
    if _act_suppresses_slot_resolution(conversation_state.last_conversational_act):
        return conversation_state, []

    slots = deepcopy(conversation_state.slots)
    pending_questions = [dict(question) for question in conversation_state.pending_questions]
    active_mission = deepcopy(conversation_state.active_mission) if conversation_state.active_mission else None
    confirmed_facts = deepcopy(conversation_state.confirmed_facts)
    derived_state = deepcopy(conversation_state.derived_state)
    resolutions: list[Dict[str, Any]] = []
    rejections: list[Dict[str, Any]] = []
    unmatched: list[Dict[str, Any]] = []

    pending_slots = _ordered_pending_slot_names(slots, pending_questions)
    explicit_matches = _explicit_slot_matches(normalized, pending_slots)
    if not explicit_matches and pending_slots:
        contextual = _contextual_slot_match(normalized, pending_slots, pending_questions)
        if contextual:
            if _clears_generic_slot_confidence_floor(contextual):
                explicit_matches.append(contextual)
            else:
                # ACA-305D-RC1 section 13: a low-confidence generic match is
                # never applied and never silently dropped -- it is recorded
                # explicitly (section 15) and turned into inert evidence for
                # MissionManager (section 9/10), never written to state here.
                rejections.append(
                    {
                        "slot": contextual["slot"],
                        "component": "conversation_state",
                        "rejected_value": deepcopy(contextual.get("value")),
                        "confidence": float(contextual.get("confidence") or 0.0),
                        "confidence_floor": GENERIC_SLOT_MATCH_CONFIDENCE_FLOOR,
                        "evidence": deepcopy(contextual.get("evidence") or {}),
                        "reason": "generic_match_below_confidence_floor",
                    }
                )
        else:
            # ACA-305D-RC1 section 7/14: distinct from a rejected match --
            # no matcher (explicit or contextual, dedicated or generic) found
            # any signal at all. Unlike a rejection, this is not evidence the
            # user answered poorly; it is evidence the message does not
            # engage with the pending question. Recorded explicitly and
            # turned into inert `suspend` evidence for MissionManager, never
            # written to state here.
            unmatched.append(
                {
                    "slot": pending_slots[0],
                    "component": "conversation_state",
                    "message": normalized,
                    "reason": "no_slot_match_found",
                }
            )

    for match in explicit_matches:
        slot_name = match["slot"]
        current_slot = slots.get(slot_name)
        if not current_slot:
            continue
        transition = _slot_transition(
            slot=current_slot,
            match=match,
            pending_questions=pending_questions,
            active_mission=active_mission,
        )
        resolutions.append(transition)
        slots[slot_name] = transition["slot_after"]
        if transition["closed"]:
            confirmed_facts[slot_name] = deepcopy(match["value"])
            pending_questions = [
                question
                for question in pending_questions
                if question.get("slot") != slot_name
            ]

    if not resolutions:
        repeated = _repeated_slot_answer(normalized, slots)
        if repeated:
            resolutions.append(repeated)

    if not resolutions and not rejections and not unmatched:
        return conversation_state, []

    if resolutions:
        active_mission = _mission_with_slots(active_mission, slots)
        # `derived_state["slot_resolution"]` is set only when a real
        # resolution occurred -- preserved exactly as it was before
        # ACA-305D-RC2/this closing sprint. `_conversation_failed_steps`
        # (a pre-existing, approved contract, conversation_fulfillment.v1)
        # treats this key's mere presence as "something legitimate
        # happened this turn, do not mark the expected step failed"
        # (conversation_state.py `_conversation_failed_steps`). Rejections
        # and unmatched evidence are NOT resolutions -- nothing was
        # answered -- so they must never make this key appear on their
        # own, or they would silently suppress that pre-existing recovery
        # mechanism for auto_claim_guidance (verified regression, fixed
        # here rather than by touching `_conversation_failed_steps` itself).
        trace = {
            "contract": "slot_resolution_trace.v1",
            "component": "conversation_state",
            "message": str(message),
            "resolutions": [dict(resolution) for resolution in resolutions],
        }
        derived_state["slot_resolution"] = trace
    if rejections or unmatched:
        derived_state["slot_resolution_evidence"] = {
            "contract": "slot_resolution_evidence_trace.v1",
            "component": "conversation_state",
            "message": str(message),
            "rejections": [dict(rejection) for rejection in rejections],
            "unmatched": [dict(item) for item in unmatched],
        }
    proposals: list[Dict[str, Any]] = []
    if rejections and active_mission:
        proposal = _slot_rejection_mission_proposal(
            active_mission=active_mission,
            rejections=rejections,
            turn=conversation_state.turn_count,
        )
        if proposal:
            proposals.append(proposal)
    if unmatched and active_mission:
        proposal = _slot_unmatched_mission_proposal(
            active_mission=active_mission,
            unmatched=unmatched,
            turn=conversation_state.turn_count,
        )
        if proposal:
            proposals.append(proposal)
    if proposals:
        derived_state["mission_transition_proposals"] = [
            *(derived_state.get("mission_transition_proposals") or []),
            *proposals,
        ]
    return (
        replace(
            conversation_state,
            slots=slots,
            active_mission=active_mission,
            confirmed_facts=confirmed_facts,
            pending_questions=pending_questions,
            derived_state=derived_state,
            projection_sources=_append_unique(
                conversation_state.projection_sources,
                "conversation_state.slot_resolution",
            ),
        ),
        resolutions,
    )


def _slot_rejection_mission_proposal(
    *,
    active_mission: Mapping[str, Any],
    rejections: Sequence[Mapping[str, Any]],
    turn: int,
) -> Dict[str, Any] | None:
    """Inert MissionTransitionProposal recording that low-confidence slot
    evidence was rejected rather than absorbed (ACA-305D-RC1 section 13).

    `mission_delta` is deliberately empty: this proposal requests no mission
    change (`resolve_pending_slot_answers` does not become a planner,
    ACA-305B section 8) -- it only makes the rejection auditable through the
    same MissionTransitionDecision trail every other proposal already uses,
    so a future evidence consumer (e.g. `abandonment_criteria` evaluation)
    has something to read. `MissionManager` remains the only component that
    could ever turn this into an actual transition.
    """

    if not rejections:
        return None
    primary = rejections[0]
    return {
        "contract": MISSION_TRANSITION_PROPOSAL_CONTRACT,
        "proposal_id": f"slot_rejection:{int(turn)}:{primary['slot']}",
        "component": "conversation_state",
        "turn": int(turn),
        "transition_type": "maintain",
        "target_mission_type": None,
        "mission_before": deepcopy(dict(active_mission)),
        "mission_delta": {},
        "evidence": {
            "evidence_kind": "slot_match_rejected",
            "rejections": [deepcopy(dict(item)) for item in rejections],
        },
        # Confidence in the rejection itself (deterministic: the underlying
        # match's own confidence was below the floor), not in the rejected
        # content -- distinct from the rejected match's own low confidence.
        "confidence": 1.0,
        "reason": "insufficient_evidence_for_slot_answer",
    }


# auto_claim_guidance already owns a complete, pre-existing, approved
# recovery authority for an unanswered expected step -- `conversation_
# fulfillment.v1` (introduced in the same commit as reformulation itself,
# c0c2bcf, and covered by its own tests, e.g. test_conversation_fulfillment.
# py::test_unanswered_expected_step_records_failure_and_recovery_action,
# which requires the mission to stay `auto_claim_guidance`/`in_progress`
# and reask via reformulation, not transition). Proposing `suspend` here for
# that mission type would contradict that already-approved contract and
# break byte-identical auto_claim_guidance behavior. This mechanism exists
# specifically for mission types with no such dedicated recovery authority
# (today: `general_orientation`).
_MISSION_TYPES_WITH_OWN_RECOVERY_AUTHORITY = {"auto_claim_guidance"}


def _slot_unmatched_mission_proposal(
    *,
    active_mission: Mapping[str, Any],
    unmatched: Sequence[Mapping[str, Any]],
    turn: int,
) -> Dict[str, Any] | None:
    """Inert `suspend` MissionTransitionProposal for a message that matched
    no pending-slot pattern at all -- explicit or contextual, dedicated or
    generic (ACA-305D-RC1 section 7, "fixture 4" root cause: distinct from a
    rejected match, this is the absence of any relevant signal). `suspend`,
    not `abandon`: a single non-engaging turn does not prove the mission was
    given up on, only that it should pause rather than keep repeating an
    unanswered question against unrelated input. MissionManager evaluates
    and may reject this like any other proposal (ACA-305B section 9); this
    function only proposes.
    """

    if not unmatched:
        return None
    if str(active_mission.get("type") or "") in _MISSION_TYPES_WITH_OWN_RECOVERY_AUTHORITY:
        return None
    return {
        "contract": MISSION_TRANSITION_PROPOSAL_CONTRACT,
        "proposal_id": f"slot_unmatched:{int(turn)}:{unmatched[0]['slot']}",
        "component": "conversation_state",
        "turn": int(turn),
        "transition_type": "suspend",
        "target_mission_type": None,
        "mission_before": deepcopy(dict(active_mission)),
        "mission_delta": {"lifecycle_status": MissionLifecycleStatus.SUSPENDED, "status": "suspended"},
        "evidence": {
            "evidence_kind": "no_slot_match_found",
            "unmatched": [deepcopy(dict(item)) for item in unmatched],
        },
        # Certainty that no matcher found any signal (a deterministic fact),
        # not a semantic judgment that the message is truly unrelated.
        "confidence": 1.0,
        "reason": "no_evidence_message_answers_pending_question",
    }


def slot_lifecycle_contract() -> Dict[str, Any]:
    return {
        "contract": "slot_lifecycle.v1",
        "statuses": sorted(VALID_SLOT_STATUSES),
        "closed_statuses": sorted(SLOT_CLOSED_STATUSES),
        "transitions": {
            status: list(next_statuses)
            for status, next_statuses in sorted(SLOT_LIFECYCLE.items())
        },
    }


def mission_lifecycle_contract() -> Dict[str, Any]:
    return {
        "contract": "mission_lifecycle.v1",
        "statuses": sorted(VALID_MISSION_LIFECYCLE_STATUSES),
        "transitions": {
            status: list(next_statuses)
            for status, next_statuses in sorted(MISSION_LIFECYCLE.items())
        },
    }


def conversational_fact_contract() -> Dict[str, Any]:
    return {
        "contract": "conversational_fact.v1",
        "required_fields": [
            "type",
            "value",
            "origin",
            "confidence",
            "mission_type",
            "acquired_turn",
            "evidence",
            "status",
            "history",
        ],
        "revision_fields": [
            "replaced_fact",
            "revision_reason",
            "revised_turn",
            "revision_evidence",
        ],
    }


def fact_lifecycle_contract() -> Dict[str, Any]:
    return {
        "contract": "fact_lifecycle.v1",
        "statuses": sorted(VALID_FACT_STATUSES),
        "active_statuses": [FactStatus.ACTIVE],
        "inactive_statuses": sorted(VALID_FACT_STATUSES - {FactStatus.ACTIVE}),
        "transitions": {
            status: list(next_statuses)
            for status, next_statuses in sorted(FACT_LIFECYCLE.items())
        },
    }


def conversational_act_contract() -> Dict[str, Any]:
    return {
        "contract": "conversational_act.v1",
        "act_types": sorted(VALID_CONVERSATIONAL_ACT_TYPES),
        "required_fields": [
            "act",
            "confidence",
            "evidence",
            "component",
            "turn",
            "reason",
            "impact",
        ],
        "turn_scoped_projection": "conversation_act_recognition",
    }


def conversational_goal_contract() -> Dict[str, Any]:
    return {
        "contract": "conversational_goal.v1",
        "strategies": sorted(VALID_CONVERSATIONAL_STRATEGIES),
        "required_fields": [
            "originating_act",
            "intention",
            "strategy",
            "success_criteria",
            "abandonment_criteria",
            "priority",
            "mission_impact",
            "evidence",
            "fulfillment",
        ],
        "turn_scoped_projection": "conversation_goal",
    }


def topic_stack_contract() -> Dict[str, Any]:
    return {
        "contract": "topic_stack.v1",
        "topic_contract": "conversation_topic.v1",
        "statuses": sorted(VALID_TOPIC_STATUSES),
        "active_statuses": sorted(TOPIC_ACTIVE_STATUSES),
        "transitions": {
            status: list(next_statuses)
            for status, next_statuses in sorted(TOPIC_LIFECYCLE.items())
        },
        "required_topic_fields": [
            "id",
            "type",
            "mission_type",
            "conversational_goal",
            "priority",
            "status",
            "created_turn",
            "last_active_turn",
            "associated_facts",
            "associated_slots",
            "summary",
        ],
        "transition_contract": "topic_stack_transition.v1",
        "owner": "conversation_state",
    }


def conversational_response_plan_contract() -> Dict[str, Any]:
    return {
        "contract": "conversational_response_plan.v1",
        "required_fields": [
            "primary_user_need",
            "secondary_needs",
            "dominant_concern",
            "response_priority",
            "next_action",
            "required_information",
            "unresolved_questions",
        ],
        "principles": {
            "cognitive_opacity": "Internal strategy and state-management decisions are introspection-only.",
            "question_justification": "Every user-facing question must have an explicit purpose.",
        },
        "turn_scoped_projection": "conversation_response_plan",
    }


def conversational_intent_model_contract() -> Dict[str, Any]:
    return {
        "contract": "conversational_intent_model.v1",
        "required_fields": [
            "explicit_questions",
            "implicit_questions",
            "dominant_concern",
            "user_goal",
            "user_assumptions",
            "missing_information",
            "response_objective",
        ],
        "purpose": "Decompose what the user wrote into practical conversational intent before response planning.",
        "turn_scoped_projection": "conversation_intent_model",
    }


def information_gain_plan_contract() -> Dict[str, Any]:
    return {
        "contract": "information_gain_plan.v1",
        "required_fields": [
            "candidate_questions",
            "expected_information_gain",
            "affected_decisions",
            "estimated_cost",
            "blocking_level",
            "clarification_priority",
            "selected_question",
        ],
        "principle": "Ask only when the answer can change a decision or unblock the next cognitive step.",
        "turn_scoped_projection": "conversation_information_gain_plan",
    }


def conversation_plan_contract() -> Dict[str, Any]:
    return {
        "contract": "conversation_plan.v1",
        "required_fields": [
            "active_plan",
            "completed_steps",
            "pending_steps",
            "abandoned_steps",
            "replanning_reason",
            "inserted_steps",
            "skipped_steps",
            "conversation_progress",
        ],
        "principle": "Conversation planning is dynamic: new evidence may complete, insert, skip or abandon steps without resetting the active goal.",
        "persistent_projection": "conversation_plan",
    }


def conversation_fulfillment_contract() -> Dict[str, Any]:
    return {
        "contract": "conversation_fulfillment.v1",
        "required_fields": [
            "fulfilled_goal",
            "fulfilled_steps",
            "pending_steps",
            "failed_steps",
            "recovery_actions",
            "fulfillment_confidence",
            "completion_reason",
        ],
        "principle": "After every response, ACA evaluates whether the conversational objective was actually satisfied and which recovery action is needed.",
        "turn_scoped_projection": "conversation_fulfillment",
    }


def model_conversational_intent(
    conversation_state: ConversationState,
    message: Any,
) -> tuple[ConversationState, Dict[str, Any]]:
    normalized = normalize_text(message)
    model = _conversational_intent_model(conversation_state, message, normalized)
    trace = {
        "contract": "conversation_intent_model_trace.v1",
        "component": "conversation_state",
        "model": deepcopy(model),
        "explicit_questions": deepcopy(model.get("explicit_questions") or []),
        "implicit_questions": deepcopy(model.get("implicit_questions") or []),
        "dominant_concern": deepcopy(model.get("dominant_concern") or {}),
        "response_objective": deepcopy(model.get("response_objective") or {}),
        "missing_information": deepcopy(model.get("missing_information") or []),
    }
    derived_state = deepcopy(conversation_state.derived_state)
    derived_state["conversation_intent_model"] = trace
    return (
        replace(
            conversation_state,
            derived_state=derived_state,
            projection_sources=_append_unique(
                conversation_state.projection_sources,
                "conversation_state.conversational_intent_model",
            ),
        ),
        model,
    )


def plan_information_gain(
    conversation_state: ConversationState,
    message: Any,
) -> tuple[ConversationState, Dict[str, Any]]:
    normalized = normalize_text(message)
    plan = _information_gain_plan(conversation_state, message, normalized)
    trace = {
        "contract": "information_gain_plan_trace.v1",
        "component": "conversation_state",
        "plan": deepcopy(plan),
        "candidate_questions": deepcopy(plan.get("candidate_questions") or []),
        "selected_question": deepcopy(plan.get("selected_question") or {}),
        "selection_reason": plan.get("selection_reason"),
        "tie_break": deepcopy(plan.get("tie_break") or {}),
        "question_count_metric": deepcopy(plan.get("question_count_metric") or {}),
    }
    derived_state = deepcopy(conversation_state.derived_state)
    derived_state["conversation_information_gain_plan"] = trace
    return (
        replace(
            conversation_state,
            derived_state=derived_state,
            projection_sources=_append_unique(
                conversation_state.projection_sources,
                "conversation_state.information_gain_plan",
            ),
        ),
        plan,
    )


def plan_conversation(
    conversation_state: ConversationState,
    message: Any,
) -> tuple[ConversationState, Dict[str, Any]]:
    normalized = normalize_text(message)
    plan = _conversation_plan(conversation_state, message, normalized)
    trace = {
        "contract": "conversation_plan_trace.v1",
        "component": "conversation_state",
        "previous_plan": deepcopy(plan.get("previous_plan") or {}),
        "plan": deepcopy(plan),
        "active_plan": deepcopy(plan.get("active_plan") or {}),
        "completed_steps": deepcopy(plan.get("completed_steps") or []),
        "pending_steps": deepcopy(plan.get("pending_steps") or []),
        "abandoned_steps": deepcopy(plan.get("abandoned_steps") or []),
        "inserted_steps": deepcopy(plan.get("inserted_steps") or []),
        "skipped_steps": deepcopy(plan.get("skipped_steps") or []),
        "replanning_reason": plan.get("replanning_reason"),
        "conversation_progress": plan.get("conversation_progress"),
    }
    derived_state = deepcopy(conversation_state.derived_state)
    derived_state["conversation_plan"] = trace
    return (
        replace(
            conversation_state,
            derived_state=derived_state,
            projection_sources=_append_unique(
                conversation_state.projection_sources,
                "conversation_state.conversation_plan",
            ),
        ),
        plan,
    )


def project_conversational_goal(
    conversation_state: ConversationState,
    *,
    source: str,
    goal_projection: Mapping[str, Any] | None = None,
    projection_metadata: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    act = dict(conversation_state.last_conversational_act or {})
    if not act:
        return {}
    return _conversational_goal_for_act(
        conversation_state,
        act,
        source=source,
        goal_projection=goal_projection,
        projection_metadata=projection_metadata,
    )


def apply_conversational_goal(
    conversation_state: ConversationState,
    goal: Mapping[str, Any],
    *,
    authority_decision: Mapping[str, Any] | None = None,
) -> tuple[ConversationState, Dict[str, Any]]:
    selected_goal = deepcopy(dict(goal or {}))
    if not selected_goal:
        return conversation_state, {}
    derived_state = deepcopy(conversation_state.derived_state)
    derived_state["conversation_goal"] = {
        "contract": "conversation_goal_trace.v1",
        "component": "conversation_state",
        "goal": deepcopy(selected_goal),
        "fulfillment": deepcopy(selected_goal.get("fulfillment") or {}),
        "authority": deepcopy(dict(authority_decision or {})),
    }
    topic_stack = _topic_stack_with_conversational_goal(
        conversation_state.topic_stack,
        goal=selected_goal,
        derived_state=derived_state,
        turn=conversation_state.turn_count,
    )
    projection_source = "conversation_state.conversational_goal"
    if (authority_decision or {}).get("authority_selected") == "semantic":
        projection_source = "semantic_projection.conversational_goal"
    return (
        replace(
            conversation_state,
            topic_stack=topic_stack,
            conversational_strategy=deepcopy(selected_goal.get("strategy") or {}),
            derived_state=derived_state,
            projection_sources=_append_unique(
                conversation_state.projection_sources,
                projection_source,
            ),
        ),
        selected_goal,
    )


def conversational_goal_state_effect(
    conversation_state: ConversationState,
) -> Dict[str, Any]:
    trace = dict(conversation_state.derived_state.get("conversation_goal") or {})
    goal = dict(trace.get("goal") or {})
    decision_fields = {
        key: deepcopy(goal.get(key))
        for key in (
            "contract",
            "originating_act",
            "act",
            "intention",
            "strategy",
            "success_criteria",
            "abandonment_criteria",
            "priority",
            "mission_impact",
            "fulfillment",
            "component",
            "turn",
        )
    }
    topic_goals = [
        deepcopy(dict(topic.get("conversational_goal") or {}))
        for topic in conversation_state.topic_stack
        if isinstance(topic, Mapping) and topic.get("conversational_goal")
    ]
    return {
        "goal": decision_fields,
        "conversational_strategy": deepcopy(conversation_state.conversational_strategy),
        "topic_goals": topic_goals,
    }


def plan_conversational_response(
    conversation_state: ConversationState,
    message: Any,
) -> tuple[ConversationState, Dict[str, Any]]:
    normalized = normalize_text(message)
    intent_model = _intent_model_from_state(conversation_state)
    needs = _detected_response_needs(conversation_state, message, normalized)
    dominant_concern = _dominant_concern_from_needs(normalized, needs, intent_model)
    primary_need = _primary_need_from(needs, dominant_concern, conversation_state)
    secondary_needs = [
        deepcopy(need)
        for need in needs
        if need.get("key") != primary_need.get("key")
    ]
    information_gain_plan = _information_gain_plan_from_state(conversation_state)
    if not information_gain_plan:
        information_gain_plan = _information_gain_plan(conversation_state, message, normalized)
    conversation_plan = _conversation_plan_from_state(conversation_state)
    if not conversation_plan:
        conversation_plan = _conversation_plan(conversation_state, message, normalized)
    required_candidates = _required_information_for_response(conversation_state, primary_need)
    required_information = _selected_required_information(
        required_candidates,
        information_gain_plan,
        conversation_plan=conversation_plan,
        primary_need=primary_need,
        conversational_act=conversation_state.last_conversational_act,
    )
    response_priority = _response_priority_for(
        primary_need=primary_need,
        secondary_needs=secondary_needs,
        required_information=required_information,
    )
    plan = {
        "contract": "conversational_response_plan.v1",
        "primary_user_need": deepcopy(primary_need),
        "secondary_needs": secondary_needs,
        "dominant_concern": deepcopy(dominant_concern),
        "intent_model": deepcopy(intent_model),
        "information_gain_plan": deepcopy(information_gain_plan),
        "conversation_plan": deepcopy(conversation_plan),
        "response_priority": response_priority,
        "next_action": _response_next_action(
            conversation_state=conversation_state,
            primary_need=primary_need,
            required_information=required_information,
        ),
        "required_information": required_information,
        "unresolved_questions": _unresolved_questions_for_response(needs, required_information),
        "natural_response_order": [
            "acknowledge_primary_concern",
            "answer_primary_need",
            "brief_reason",
            "concrete_next_step",
        ],
        "principles": {
            "cognitive_opacity": True,
            "question_justification": True,
        },
        "evidence": {
            "message": str(message),
            "normalized_message": normalized,
            "active_topic": deepcopy(_active_topic_from_stack(conversation_state.topic_stack) or {}),
            "active_mission": deepcopy(conversation_state.active_mission or {}),
            "conversational_act": deepcopy(conversation_state.last_conversational_act or {}),
            "intent_model": deepcopy(intent_model),
            "information_gain_plan": deepcopy(information_gain_plan),
            "conversation_plan": deepcopy(conversation_plan),
        },
        "component": "conversation_state",
        "turn": int(conversation_state.turn_count),
    }
    trace = {
        "contract": "conversation_response_plan_trace.v1",
        "component": "conversation_state",
        "plan": deepcopy(plan),
        "primary_user_need": deepcopy(primary_need),
        "dominant_concern": deepcopy(dominant_concern),
        "intent_model": deepcopy(intent_model),
        "information_gain_plan": deepcopy(information_gain_plan),
        "conversation_plan": deepcopy(conversation_plan),
        "response_priority": list(response_priority),
        "question_justifications": [
            {
                "question": item.get("question"),
                "purpose": item.get("purpose"),
                "slot": item.get("slot"),
            }
            for item in required_information
        ],
    }
    derived_state = deepcopy(conversation_state.derived_state)
    derived_state["conversation_response_plan"] = trace
    return (
        replace(
            conversation_state,
            derived_state=derived_state,
            projection_sources=_append_unique(
                conversation_state.projection_sources,
                "conversation_state.conversational_response_plan",
            ),
        ),
        plan,
    )


def _information_gain_plan(
    conversation_state: ConversationState,
    message: Any,
    normalized: str,
) -> Dict[str, Any]:
    intent_model = _intent_model_from_state(conversation_state)
    needs = _detected_response_needs(conversation_state, message, normalized)
    dominant_concern = _dominant_concern_from_needs(normalized, needs, intent_model)
    primary_need = _primary_need_from(needs, dominant_concern, conversation_state)
    candidate_questions = _scored_clarification_candidates(
        _candidate_clarification_questions(
            conversation_state=conversation_state,
            primary_need=primary_need,
            intent_model=intent_model,
        ),
        primary_need=primary_need,
    )
    selected_question, selection_reason, tie_break = _select_clarification_question(candidate_questions)
    return {
        "contract": "information_gain_plan.v1",
        "candidate_questions": candidate_questions,
        "expected_information_gain": float(selected_question.get("expected_information_gain") or 0.0),
        "affected_decisions": list(selected_question.get("affected_decisions") or []),
        "estimated_cost": float(selected_question.get("estimated_cost") or 0.0),
        "blocking_level": str(selected_question.get("blocking_level") or "none"),
        "clarification_priority": float(selected_question.get("clarification_priority") or 0.0),
        "selected_question": deepcopy(selected_question),
        "selection_reason": selection_reason,
        "tie_break": tie_break,
        "can_continue_without_question": not bool(selected_question),
        "question_count_metric": {
            "candidate_question_count": len(candidate_questions),
            "selected_question_count": 1 if selected_question else 0,
            "avoided_question_count": max(len(candidate_questions) - (1 if selected_question else 0), 0),
        },
        "evidence": {
            "message": str(message),
            "normalized_message": normalized,
            "primary_user_need": deepcopy(primary_need),
            "dominant_concern": deepcopy(dominant_concern),
            "intent_missing_information": deepcopy(intent_model.get("missing_information") or []),
        },
        "component": "conversation_state",
        "turn": int(conversation_state.turn_count),
    }


def _information_gain_plan_from_state(conversation_state: ConversationState) -> Dict[str, Any]:
    trace = conversation_state.derived_state.get("conversation_information_gain_plan")
    if isinstance(trace, Mapping):
        plan = trace.get("plan")
        if isinstance(plan, Mapping):
            return deepcopy(dict(plan))
        return deepcopy(dict(trace))
    return {}


def _conversation_plan(
    conversation_state: ConversationState,
    message: Any,
    normalized: str,
) -> Dict[str, Any]:
    previous_plan = _previous_conversation_plan_for_replanning(conversation_state)
    mission = deepcopy(conversation_state.active_mission or {})
    fact_values = _active_fact_values(conversation_state.confirmed_facts)
    intent_model = _intent_model_from_state(conversation_state)
    information_gain_plan = _information_gain_plan_from_state(conversation_state)
    base_steps = _mission_conversation_steps(
        mission=mission,
        slots=conversation_state.slots,
        facts=fact_values,
    )
    inserted_steps = _inserted_conversation_steps(
        conversation_state=conversation_state,
        message=message,
        normalized=normalized,
        intent_model=intent_model,
    )
    active_steps = _conversation_steps_with_insertions(base_steps, inserted_steps)
    previous_steps = _active_steps_from_previous_plan(previous_plan)
    completed_steps = [deepcopy(step) for step in active_steps if step.get("status") == "completed"]
    pending_steps = [deepcopy(step) for step in active_steps if step.get("status") == "pending"]
    abandoned_steps = _abandoned_conversation_steps(previous_steps, active_steps)
    skipped_steps = _skipped_conversation_steps(
        previous_steps=previous_steps,
        active_steps=active_steps,
        information_gain_plan=information_gain_plan,
    )
    replanning_reason = _conversation_replanning_reason(
        previous_plan=previous_plan,
        inserted_steps=inserted_steps,
        completed_steps=completed_steps,
        abandoned_steps=abandoned_steps,
        skipped_steps=skipped_steps,
        derived_state=conversation_state.derived_state,
    )
    conversation_progress = _conversation_progress(active_steps, mission)
    current_step = _current_conversation_step(active_steps)
    return {
        "contract": "conversation_plan.v1",
        "active_plan": {
            "contract": "active_conversation_plan.v1",
            "mission_type": mission.get("type"),
            "mission_goal": mission.get("goal"),
            "current_step": deepcopy(current_step),
            "steps": active_steps,
            "source": "conversation_state",
        },
        "completed_steps": completed_steps,
        "pending_steps": pending_steps,
        "abandoned_steps": abandoned_steps,
        "replanning_reason": replanning_reason,
        "inserted_steps": inserted_steps,
        "skipped_steps": skipped_steps,
        "conversation_progress": conversation_progress,
        "previous_plan": deepcopy(previous_plan),
        "evidence": {
            "message": str(message),
            "normalized_message": normalized,
            "active_mission": mission,
            "facts": deepcopy(fact_values),
            "intent_model": deepcopy(intent_model),
            "information_gain_plan": deepcopy(information_gain_plan),
        },
        "component": "conversation_state",
        "turn": int(conversation_state.turn_count),
    }


def _conversation_plan_from_state(conversation_state: ConversationState) -> Dict[str, Any]:
    trace = conversation_state.derived_state.get("conversation_plan")
    if isinstance(trace, Mapping):
        plan = trace.get("plan")
        if isinstance(plan, Mapping):
            return deepcopy(dict(plan))
        return deepcopy(dict(trace))
    return {}


def _previous_conversation_plan_for_replanning(conversation_state: ConversationState) -> Dict[str, Any]:
    trace = conversation_state.derived_state.get("conversation_plan")
    if not isinstance(trace, Mapping):
        return {}
    plan = trace.get("plan")
    if not isinstance(plan, Mapping):
        return deepcopy(dict(trace))
    if int(plan.get("turn") or 0) == int(conversation_state.turn_count):
        previous = plan.get("previous_plan")
        return deepcopy(dict(previous)) if isinstance(previous, Mapping) else {}
    return deepcopy(dict(plan))


def _mission_conversation_steps(
    *,
    mission: Mapping[str, Any],
    slots: Mapping[str, Mapping[str, Any]],
    facts: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    mission_type = str(mission.get("type") or "")
    if mission_type == "auto_claim_guidance":
        steps = [
            _conversation_step(
                step_id="confirm_injuries",
                step_type="slot",
                label="confirmar si hubo lesionados",
                status=_step_status_for_known_value(facts.get("injuries"), slots.get("injuries")),
                mission=mission,
                slot="injuries",
                decision="safety_and_escalation_path",
                order=10,
            ),
            _conversation_step(
                step_id="confirm_user_role",
                step_type="slot",
                label="confirmar si es asegurado o tercero",
                status=_step_status_for_known_value(facts.get("user_role"), slots.get("user_role")),
                mission=mission,
                slot="user_role",
                decision="claim_guidance_path",
                order=20,
            ),
            _conversation_step(
                step_id="confirm_claim_report_loaded",
                step_type="fact",
                label="confirmar si la denuncia esta cargada",
                status=_step_status_for_boolean_fact(facts.get("claim_report_loaded")),
                mission=mission,
                fact="claim_report_loaded",
                decision="claim_report_or_documentation_path",
                order=30,
            ),
            _conversation_step(
                step_id="confirm_documentation_available",
                step_type="fact",
                label="confirmar si tiene documentacion",
                status=_step_status_for_boolean_fact(facts.get("documentation_available")),
                mission=mission,
                fact="documentation_available",
                decision="claim_follow_up_path",
                order=40,
            ),
            _conversation_step(
                step_id="provide_next_step_guidance",
                step_type="response",
                label="indicar siguiente paso util",
                status="completed" if str(mission.get("next_act") or "") == "provide_next_step_guidance" else "pending",
                mission=mission,
                decision="final_guidance",
                order=50,
            ),
        ]
        if facts.get("claim_report_loaded") is False:
            steps.insert(
                3,
                _conversation_step(
                    step_id="complete_claim_report",
                    step_type="repair_step",
                    label="resolver carga de denuncia antes de avanzar",
                    status="pending",
                    mission=mission,
                    fact="claim_report_loaded",
                    decision="claim_report_or_documentation_path",
                    order=35,
                ),
            )
        if facts.get("documentation_available") is False:
            steps.insert(
                4,
                _conversation_step(
                    step_id="complete_documentation",
                    step_type="repair_step",
                    label="completar documentacion antes de seguimiento",
                    status="pending",
                    mission=mission,
                    fact="documentation_available",
                    decision="claim_follow_up_path",
                    order=45,
                ),
            )
        return sorted(steps, key=lambda item: int(item.get("order", 100) or 100))
    if mission_type == "knowledge_lookup":
        return [
            _conversation_step(
                step_id="provide_concept_explanation",
                step_type="response",
                label="explicar concepto usando evidencia",
                status="pending",
                mission=mission,
                decision="knowledge_response",
                order=10,
            )
        ]
    if mission_type:
        return [
            _conversation_step(
                step_id="understand_user_need",
                step_type="clarification",
                label="comprender necesidad principal",
                status=_step_status_for_known_value(facts.get("user_need"), slots.get("user_need")),
                mission=mission,
                slot="user_need",
                decision="response_prioritization",
                order=10,
            )
        ]
    return []


def _conversation_step(
    *,
    step_id: str,
    step_type: str,
    label: str,
    status: str,
    mission: Mapping[str, Any],
    decision: str,
    order: int,
    slot: str | None = None,
    fact: str | None = None,
) -> Dict[str, Any]:
    step = {
        "contract": "conversation_plan_step.v1",
        "id": step_id,
        "type": step_type,
        "label": label,
        "status": status,
        "mission_type": mission.get("type"),
        "mission_next_act": mission.get("next_act"),
        "decision": decision,
        "order": int(order),
    }
    if slot:
        step["slot"] = slot
    if fact:
        step["fact"] = fact
    return step


def _step_status_for_known_value(value: Any, slot: Mapping[str, Any] | None) -> str:
    if value is not None:
        return "completed"
    if slot and slot.get("status") in SLOT_CLOSED_STATUSES:
        return "completed"
    return "pending"


def _step_status_for_boolean_fact(value: Any) -> str:
    if value is True:
        return "completed"
    return "pending"


def _inserted_conversation_steps(
    *,
    conversation_state: ConversationState,
    message: Any,
    normalized: str,
    intent_model: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    mission = conversation_state.active_mission or {}
    if not mission:
        return []
    primary_need = str(((intent_model.get("response_objective") or {}).get("need_key")) or "")
    inserted: list[Dict[str, Any]] = []
    if primary_need in {"claim_status_or_payment", "claim_contact_progress"} or _mentions_status_or_payment_need(normalized):
        inserted.append(
            _conversation_step(
                step_id="answer_lateral_process_timing",
                step_type="side_question",
                label="responder consulta lateral sobre tiempos o avance",
                status="pending",
                mission=mission,
                decision="process_progress_confidence",
                order=5,
            )
        )
    if primary_need in {"vehicle_repair_authorization", "photo_upload_status", "photo_requirement_confidence"} and mission.get("type") == "auto_claim_guidance":
        inserted.append(
            _conversation_step(
                step_id=f"answer_lateral_{primary_need}",
                step_type="side_question",
                label=str((intent_model.get("response_objective") or {}).get("label") or "responder consulta lateral"),
                status="pending",
                mission=mission,
                decision=primary_need,
                order=5,
            )
        )
    if str((conversation_state.last_conversational_act or {}).get("act") or "") == ConversationalActType.TOPIC_SHIFT:
        inserted.append(
            _conversation_step(
                step_id="handle_topic_shift",
                step_type="focus_transition",
                label="administrar cambio o recuperacion de foco",
                status="pending",
                mission=mission,
                decision="focus_management",
                order=4,
            )
        )
    return _dedupe_steps(inserted)


def _conversation_steps_with_insertions(
    base_steps: Sequence[Mapping[str, Any]],
    inserted_steps: Sequence[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    return sorted(
        [deepcopy(dict(step)) for step in inserted_steps] + [deepcopy(dict(step)) for step in base_steps],
        key=lambda item: int(item.get("order", 100) or 100),
    )


def _active_steps_from_previous_plan(previous_plan: Mapping[str, Any]) -> list[Dict[str, Any]]:
    active_plan = previous_plan.get("active_plan") if isinstance(previous_plan, Mapping) else None
    if not isinstance(active_plan, Mapping):
        return []
    steps = active_plan.get("steps")
    if not isinstance(steps, Sequence) or isinstance(steps, (str, bytes)):
        return []
    return [deepcopy(dict(step)) for step in steps if isinstance(step, Mapping)]


def _abandoned_conversation_steps(
    previous_steps: Sequence[Mapping[str, Any]],
    active_steps: Sequence[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    active_ids = {str(step.get("id") or "") for step in active_steps}
    abandoned = []
    for step in previous_steps:
        step_id = str(step.get("id") or "")
        if not step_id or step_id in active_ids:
            continue
        if step.get("status") == "completed":
            continue
        item = deepcopy(dict(step))
        item["status"] = "abandoned"
        item["reason"] = "not_present_after_replanning"
        abandoned.append(item)
    return abandoned


def _skipped_conversation_steps(
    *,
    previous_steps: Sequence[Mapping[str, Any]],
    active_steps: Sequence[Mapping[str, Any]],
    information_gain_plan: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    skipped: list[Dict[str, Any]] = []
    selected_slot = str(((information_gain_plan.get("selected_question") or {}).get("slot")) or "")
    for candidate in information_gain_plan.get("candidate_questions") or []:
        if not isinstance(candidate, Mapping):
            continue
        slot = str(candidate.get("slot") or "")
        if not slot or slot == selected_slot:
            continue
        matching_step = _step_for_slot_or_fact(active_steps, slot)
        if matching_step and matching_step.get("status") == "pending":
            item = deepcopy(dict(matching_step))
            item["status"] = "skipped_for_now"
            item["reason"] = "lower_information_gain_than_selected_question"
            item["candidate_question"] = deepcopy(dict(candidate))
            skipped.append(item)
    previous_by_id = {str(step.get("id") or ""): dict(step) for step in previous_steps if step.get("id")}
    for step in active_steps:
        step_id = str(step.get("id") or "")
        previous = previous_by_id.get(step_id)
        if not previous:
            continue
        if (
            previous.get("status") == "pending"
            and step.get("status") == "completed"
            and step.get("type") in {"slot", "fact", "clarification"}
        ):
            item = deepcopy(dict(step))
            item["status"] = "skipped_by_new_evidence"
            item["reason"] = "user_supplied_information_before_question_was_asked"
            skipped.append(item)
    return _dedupe_steps(skipped)


def _step_for_slot_or_fact(steps: Sequence[Mapping[str, Any]], key: str) -> Dict[str, Any] | None:
    for step in steps:
        if step.get("slot") == key or step.get("fact") == key:
            return deepcopy(dict(step))
    return None


def _conversation_replanning_reason(
    *,
    previous_plan: Mapping[str, Any],
    inserted_steps: Sequence[Mapping[str, Any]],
    completed_steps: Sequence[Mapping[str, Any]],
    abandoned_steps: Sequence[Mapping[str, Any]],
    skipped_steps: Sequence[Mapping[str, Any]],
    derived_state: Mapping[str, Any],
) -> str:
    if not previous_plan:
        return "plan_initialized"
    if inserted_steps:
        return "side_step_inserted_preserve_active_plan"
    if derived_state.get("fact_revision"):
        return "facts_revised_replan_required"
    if derived_state.get("fact_assimilation") or derived_state.get("mission_advancement"):
        if skipped_steps:
            return "new_evidence_completed_or_skipped_steps"
        if completed_steps:
            return "new_evidence_advanced_plan"
        return "new_evidence_reviewed_plan"
    if abandoned_steps:
        return "steps_abandoned_after_replanning"
    if skipped_steps:
        return "question_selection_skipped_lower_value_steps"
    return "plan_still_valid"


def _conversation_progress(steps: Sequence[Mapping[str, Any]], mission: Mapping[str, Any]) -> Dict[str, Any]:
    total = len([step for step in steps if step.get("type") != "side_question"])
    completed = len([step for step in steps if step.get("type") != "side_question" and step.get("status") == "completed"])
    ratio = round(completed / total, 4) if total else float(mission.get("progress") or 0.0)
    mission_progress = float(mission.get("progress") or 0.0)
    return {
        "completed_steps": completed,
        "total_steps": total,
        "ratio": max(ratio, round(mission_progress, 4)),
        "mission_progress": round(mission_progress, 4),
    }


def _current_conversation_step(steps: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    for step in steps:
        if step.get("status") == "pending":
            return deepcopy(dict(step))
    return {}


def _dedupe_steps(steps: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    by_id: Dict[str, Dict[str, Any]] = {}
    for step in steps:
        step_id = str(step.get("id") or "")
        if not step_id:
            continue
        by_id[step_id] = deepcopy(dict(step))
    return list(by_id.values())


def _candidate_clarification_questions(
    *,
    conversation_state: ConversationState,
    primary_need: Mapping[str, Any],
    intent_model: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    candidates: list[Dict[str, Any]] = []
    seen_slots: set[str] = set()
    for item in _required_information_for_response(conversation_state, primary_need):
        candidate = _candidate_from_required_information(item)
        if not candidate:
            continue
        slot = str(candidate.get("slot") or "")
        if not slot or slot in seen_slots:
            continue
        candidates.append(candidate)
        seen_slots.add(slot)

    fact_values = _active_fact_values(conversation_state.confirmed_facts)
    for item in intent_model.get("missing_information") or []:
        if not isinstance(item, Mapping):
            continue
        key = str(item.get("key") or "")
        if not key or key in seen_slots:
            continue
        if fact_values.get(key) is not None:
            continue
        candidate = _candidate_from_missing_information(item, primary_need)
        if not candidate:
            continue
        candidates.append(candidate)
        seen_slots.add(key)
    return candidates


def _candidate_from_required_information(item: Mapping[str, Any]) -> Dict[str, Any]:
    slot = str(item.get("slot") or "")
    if not slot:
        return {}
    source_question = dict(item.get("source_question") or {})
    source = str(source_question.get("source") or "pending_question")
    return {
        "contract": "candidate_clarification_question.v1",
        "id": f"{slot}:{source}",
        "slot": slot,
        "question": str(item.get("question") or _justified_question_for_slot(slot)),
        "purpose": str(item.get("purpose") or "tomar la siguiente decision sin inventar datos"),
        "needed_for": str(item.get("needed_for") or _question_needed_for_slot(slot)),
        "source": source,
        "priority": int(item.get("priority", _slot_priority(slot)) or _slot_priority(slot)),
        "source_question": deepcopy(source_question),
    }


def _candidate_from_missing_information(
    item: Mapping[str, Any],
    primary_need: Mapping[str, Any],
) -> Dict[str, Any]:
    key = str(item.get("key") or "")
    question = _question_for_missing_information(key)
    if not key or not question:
        return {}
    return {
        "contract": "candidate_clarification_question.v1",
        "id": f"{key}:intent_missing_information",
        "slot": key,
        "question": question,
        "purpose": _purpose_for_missing_information(key, item, primary_need),
        "needed_for": _decision_for_missing_information(key, primary_need),
        "source": "intent_missing_information",
        "priority": _missing_information_priority(key),
        "source_question": deepcopy(dict(item)),
    }


def _scored_clarification_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    primary_need: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    scored: list[Dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        slot = str(candidate.get("slot") or "")
        source = str(candidate.get("source") or "")
        profile = _information_gain_profile(slot, source, primary_need)
        priority = int(candidate.get("priority", _slot_priority(slot)) or _slot_priority(slot))
        clarification_priority = round(
            float(profile["expected_information_gain"])
            + _blocking_weight(str(profile["blocking_level"]))
            - float(profile["estimated_cost"]),
            4,
        )
        item = deepcopy(dict(candidate))
        item.update(
            {
                "expected_information_gain": round(float(profile["expected_information_gain"]), 4),
                "affected_decisions": list(profile["affected_decisions"]),
                "estimated_cost": round(float(profile["estimated_cost"]), 4),
                "blocking_level": str(profile["blocking_level"]),
                "clarification_priority": clarification_priority,
                "selection_threshold": float(profile["selection_threshold"]),
                "can_continue_without_answer": bool(profile["can_continue_without_answer"]),
                "order": index,
                "tie_breakers": {
                    "estimated_cost": round(float(profile["estimated_cost"]), 4),
                    "priority": priority,
                    "source_rank": _question_source_rank(source),
                    "order": index,
                },
            }
        )
        scored.append(item)
    return scored


def _information_gain_profile(
    slot: str,
    source: str,
    primary_need: Mapping[str, Any],
) -> Dict[str, Any]:
    primary_key = str(primary_need.get("key") or "")
    if slot == "injuries":
        return _gain_profile(0.95, 0.18, "critical", ["safety_and_escalation_path"], 0.6, False)
    if slot == "user_role":
        return _gain_profile(0.82, 0.25, "high", ["claim_guidance_path"], 0.62, False)
    if slot in {"claim_report_loaded", "documentation_available"} and source != "intent_missing_information":
        return _gain_profile(0.74, 0.2, "medium", [_question_needed_for_slot(slot)], 0.62, False)
    if slot == "claim_authorization_status" and primary_key == "vehicle_repair_authorization":
        return _gain_profile(0.76, 0.25, "medium", ["repair_authorization_guidance"], 0.62, False)
    if slot == "photo_upload_evidence" and primary_key == "photo_upload_status":
        return _gain_profile(0.82, 0.28, "medium", ["photo_upload_verification"], 0.62, False)
    if slot == "reference_target":
        return _gain_profile(0.9, 0.18, "high", ["reference_resolution"], 0.62, False)
    if slot in {"claim_report_loaded", "documentation_complete"} and source == "intent_missing_information":
        return _gain_profile(0.55, 0.2, "low", ["process_progress_confidence"], 0.62, True)
    if slot == "damage_evidence_available":
        return _gain_profile(0.64, 0.28, "low", ["evidence_preservation"], 0.62, True)
    if slot in {"claim_type", "channel_checklist"}:
        return _gain_profile(0.5, 0.3, "none", ["photo_requirement_confidence"], 0.62, True)
    if slot == "user_need":
        return _gain_profile(0.72, 0.22, "medium", ["response_prioritization"], 0.62, False)
    return _gain_profile(0.55, 0.28, "low", [_question_needed_for_slot(slot)], 0.62, True)


def _gain_profile(
    expected_information_gain: float,
    estimated_cost: float,
    blocking_level: str,
    affected_decisions: Sequence[str],
    selection_threshold: float,
    can_continue_without_answer: bool,
) -> Dict[str, Any]:
    return {
        "expected_information_gain": expected_information_gain,
        "estimated_cost": estimated_cost,
        "blocking_level": blocking_level,
        "affected_decisions": list(affected_decisions),
        "selection_threshold": selection_threshold,
        "can_continue_without_answer": can_continue_without_answer,
    }


def _blocking_weight(blocking_level: str) -> float:
    return {
        "critical": 0.35,
        "high": 0.25,
        "medium": 0.15,
        "low": 0.05,
        "none": 0.0,
    }.get(blocking_level, 0.0)


def _question_source_rank(source: str) -> int:
    return {
        "active_mission": 0,
        "mission_next_act": 1,
        "pending_question": 2,
        "intent_missing_information": 3,
    }.get(source, 9)


def _select_clarification_question(
    candidate_questions: Sequence[Mapping[str, Any]],
) -> tuple[Dict[str, Any], str, Dict[str, Any]]:
    eligible = [
        deepcopy(dict(candidate))
        for candidate in candidate_questions
        if str(candidate.get("blocking_level") or "none") != "none"
        and float(candidate.get("clarification_priority") or 0.0) >= float(candidate.get("selection_threshold") or 0.62)
    ]
    if not eligible:
        return {}, "no_candidate_changes_current_decision_enough", {}
    ordered = sorted(
        eligible,
        key=lambda item: (
            -float(item.get("clarification_priority") or 0.0),
            float(item.get("estimated_cost") or 0.0),
            _int_with_default((item.get("tie_breakers") or {}).get("source_rank"), 9),
            _int_with_default(item.get("priority"), 100),
            _int_with_default((item.get("tie_breakers") or {}).get("order"), 1000),
        ),
    )
    selected = deepcopy(dict(ordered[0]))
    max_priority = float(selected.get("clarification_priority") or 0.0)
    tied = [
        dict(item)
        for item in ordered
        if abs(float(item.get("clarification_priority") or 0.0) - max_priority) < 0.0001
    ]
    tie_break = {}
    selection_reason = "highest_information_gain"
    if len(tied) > 1:
        selection_reason = "highest_information_gain_with_deterministic_tie_break"
        tie_break = {
            "candidate_slots": [str(item.get("slot") or "") for item in tied],
            "criteria": ["lower_estimated_cost", "source_rank", "slot_priority", "stable_order"],
            "selected_slot": selected.get("slot"),
        }
    return selected, selection_reason, tie_break


def _int_with_default(value: Any, default: int) -> int:
    if value is None:
        return default
    return int(value)


def _selected_required_information(
    required_candidates: Sequence[Mapping[str, Any]],
    information_gain_plan: Mapping[str, Any],
    *,
    conversation_plan: Mapping[str, Any] | None = None,
    primary_need: Mapping[str, Any] | None = None,
    conversational_act: Mapping[str, Any] | None = None,
) -> list[Dict[str, Any]]:
    selected = dict(information_gain_plan.get("selected_question") or {})
    if not selected:
        return []
    selected_slot = str(selected.get("slot") or "")
    for item in required_candidates:
        if str(item.get("slot") or "") == selected_slot:
            chosen = deepcopy(dict(item))
            chosen["information_gain"] = _selected_question_information_gain(selected)
            chosen = _maybe_reformulate_required_question(
                chosen,
                selected=selected,
                conversation_plan=conversation_plan or {},
                primary_need=primary_need or {},
                conversational_act=conversational_act or {},
            )
            return [chosen]
    return [
        _maybe_reformulate_required_question(
            _required_information_from_selected_question(selected),
            selected=selected,
            conversation_plan=conversation_plan or {},
            primary_need=primary_need or {},
            conversational_act=conversational_act or {},
        )
    ]


def _maybe_reformulate_required_question(
    required: Mapping[str, Any],
    *,
    selected: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
    primary_need: Mapping[str, Any],
    conversational_act: Mapping[str, Any],
) -> Dict[str, Any]:
    item = deepcopy(dict(required))
    slot = str(item.get("slot") or selected.get("slot") or "")
    if not slot:
        return item
    if not _should_reformulate_selected_question(
        slot,
        conversation_plan=conversation_plan,
        conversational_act=conversational_act,
    ):
        return item
    mission_type = str((conversation_plan.get("active_plan") or {}).get("mission_type") or "")
    reformulated = _reformulated_question_for_slot(slot, primary_need=primary_need, mission_type=mission_type)
    if not reformulated:
        return item
    item["question"] = reformulated
    item["question_was_reformulated"] = True
    item["reformulated_from"] = str(selected.get("question") or required.get("question") or "")
    item["reformulation_reason"] = "same_information_still_needed_after_unanswered_or_ambiguous_turn"
    return item


def _should_reformulate_selected_question(
    slot: str,
    *,
    conversation_plan: Mapping[str, Any],
    conversational_act: Mapping[str, Any],
) -> bool:
    reason = str(conversation_plan.get("replanning_reason") or "")
    if reason == "side_step_inserted_preserve_active_plan":
        return False
    previous_current = dict(((conversation_plan.get("previous_plan") or {}).get("active_plan") or {}).get("current_step") or {})
    if str(previous_current.get("slot") or "") == slot:
        return True
    act = str(conversational_act.get("act") or "")
    return act in {
        ConversationalActType.CONTINUATION,
        ConversationalActType.CLARIFICATION,
        ConversationalActType.CLARIFICATION_REQUEST,
    }


_AUTO_CLAIM_GUIDANCE_REFORMULATION_SLOTS = {
    "injuries",
    "user_role",
    "claim_report_loaded",
    "documentation_available",
}


def _reformulated_question_for_slot(
    slot: str,
    *,
    primary_need: Mapping[str, Any],
    mission_type: str = "",
) -> str:
    """Reworded question for a slot the plan is asking again (ACA-305D-RC3).

    Content is gated by `mission_type`, not just `slot` name: the four
    `auto_claim_guidance` slots below only ever reformulate for that
    mission, and `user_need` -- `general_orientation`'s own slot since the
    project's bootstrap commit (ACA-305, "user_need origin" finding) --
    never receives domain vocabulary from any other mission. Reformulation
    always derives from the currently active mission, never from a slot
    name alone.
    """

    primary_key = str(primary_need.get("key") or "")
    if mission_type == "auto_claim_guidance" and slot in _AUTO_CLAIM_GUIDANCE_REFORMULATION_SLOTS:
        if slot == "injuries":
            return "Recordas si alguna persona resulto herida o necesito atencion medica despues del choque?"
        if slot == "user_role":
            return "Para seguir por el circuito correcto, el seguro Galicia es tuyo o estas reclamando como tercero?"
        if slot == "claim_report_loaded":
            if primary_key == "claim_status_or_payment":
                return "Para ubicar mejor los tiempos, la denuncia ya esta cargada o figura cargada en el canal?"
            if primary_key == "photo_upload_status":
                return "Para revisar las fotos en el lugar correcto, la denuncia ya esta cargada o figura cargada en el canal?"
            return "Para seguir con el tramite, la denuncia ya esta cargada o figura cargada en el canal?"
        if slot == "documentation_available":
            return "Tenes a mano fotos, presupuesto y la documentacion que te pidieron para el tramite?"
    if slot == "user_need":
        return "Contame con tus palabras que necesitas resolver, asi te puedo orientar mejor."
    return ""


def _selected_question_information_gain(selected: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "expected_information_gain": float(selected.get("expected_information_gain") or 0.0),
        "affected_decisions": list(selected.get("affected_decisions") or []),
        "estimated_cost": float(selected.get("estimated_cost") or 0.0),
        "blocking_level": str(selected.get("blocking_level") or "none"),
        "clarification_priority": float(selected.get("clarification_priority") or 0.0),
    }


def _required_information_from_selected_question(selected: Mapping[str, Any]) -> Dict[str, Any]:
    slot = str(selected.get("slot") or "")
    return {
        "slot": slot,
        "question": str(selected.get("question") or _justified_question_for_slot(slot)),
        "purpose": str(selected.get("purpose") or "tomar la siguiente decision sin inventar datos"),
        "needed_for": str(selected.get("needed_for") or (selected.get("affected_decisions") or ["next_action_selection"])[0]),
        "priority": int(selected.get("priority", _slot_priority(slot)) or _slot_priority(slot)),
        "source_question": deepcopy(dict(selected.get("source_question") or {})),
        "information_gain": _selected_question_information_gain(selected),
    }


def _question_for_missing_information(key: str) -> str:
    return {
        "claim_authorization_status": "Ya tenes autorizacion o indicacion de la aseguradora para avanzar con el arreglo?",
        "damage_evidence_available": "Tenes fotos, presupuesto o algun respaldo del dano antes de arreglarlo?",
        "claim_report_loaded": "La denuncia ya esta cargada?",
        "documentation_complete": "La documentacion quedo completa?",
        "claim_type": "Que tipo de siniestro fue?",
        "channel_checklist": "El canal te muestra alguna observacion o pendiente?",
        "reference_target": "A que te referis con eso?",
    }.get(key, "")


def _purpose_for_missing_information(
    key: str,
    item: Mapping[str, Any],
    primary_need: Mapping[str, Any],
) -> str:
    if key == "claim_authorization_status":
        return "saber si conviene esperar una indicacion antes de reparar"
    if key == "damage_evidence_available":
        return "preservar evidencia si necesitas avanzar con el arreglo"
    if key == "reference_target":
        return "responder sobre el tema correcto"
    purpose = str(item.get("purpose") or "")
    if purpose:
        return purpose
    return _question_purpose_for_slot(key, primary_need)


def _decision_for_missing_information(
    key: str,
    primary_need: Mapping[str, Any],
) -> str:
    return {
        "claim_authorization_status": "repair_authorization_guidance",
        "damage_evidence_available": "evidence_preservation",
        "claim_report_loaded": "process_progress_confidence",
        "documentation_complete": "process_progress_confidence",
        "claim_type": "photo_requirement_confidence",
        "channel_checklist": "photo_requirement_confidence",
        "reference_target": "reference_resolution",
    }.get(key, str(primary_need.get("key") or "next_action_selection"))


def _missing_information_priority(key: str) -> int:
    return {
        "reference_target": 5,
        "claim_authorization_status": 28,
        "damage_evidence_available": 38,
        "claim_report_loaded": 45,
        "documentation_complete": 50,
        "claim_type": 70,
        "channel_checklist": 75,
    }.get(key, 100)


def _detected_response_needs(
    conversation_state: ConversationState,
    message: Any,
    normalized: str,
) -> list[Dict[str, Any]]:
    needs: list[Dict[str, Any]] = []
    intent_model = _intent_model_from_state(conversation_state)
    objective = dict(intent_model.get("response_objective") or {})
    if objective.get("need_key"):
        needs.append(
            _response_need(
                key=str(objective["need_key"]),
                label=str(objective.get("label") or objective.get("objective") or "resolver necesidad implicita"),
                confidence=float(objective.get("confidence") or 0.86),
                source="conversation_intent_model",
                evidence=objective.get("evidence") or intent_model.get("evidence") or str(message),
            )
        )
    if _mentions_vehicle_repair_need(normalized):
        needs.append(
            _response_need(
                key="vehicle_repair_authorization",
                label="saber si puede arreglar el auto sin perjudicar el tramite",
                confidence=0.9,
                source="user_message",
                evidence=str(message),
            )
        )
    if _mentions_no_photo_request(normalized):
        needs.append(
            _response_need(
                key="photo_requirement_confidence",
                label="saber si no haber recibido pedido de fotos significa que hizo algo mal",
                confidence=0.88,
                source="user_message",
                evidence=str(message),
            )
        )
    if _mentions_photo_upload_need(normalized):
        needs.append(
            _response_need(
                key="photo_upload_status",
                label="verificar si las fotos fueron enviadas",
                confidence=0.82,
                source="user_message",
                evidence=str(message),
            )
        )
    if _mentions_contact_timing_need(normalized):
        needs.append(
            _response_need(
                key="claim_contact_progress",
                label="saber si el caso sigue correctamente el proceso",
                confidence=0.84,
                source="user_message",
                evidence=str(message),
            )
        )
    if _mentions_claim_report_need(normalized):
        needs.append(
            _response_need(
                key="claim_report_status",
                label="saber si la denuncia esta cargada o como seguir",
                confidence=0.78,
                source="user_message",
                evidence=str(message),
            )
        )
    if _mentions_documentation_need(normalized):
        needs.append(
            _response_need(
                key="documentation_guidance",
                label="saber que documentacion hace falta",
                confidence=0.76,
                source="user_message",
                evidence=str(message),
            )
        )
    if _mentions_status_or_payment_need(normalized):
        needs.append(
            _response_need(
                key="claim_status_or_payment",
                label="entender estado, plazos o pago del siniestro",
                confidence=0.74,
                source="user_message",
                evidence=str(message),
            )
        )
    if not needs and (conversation_state.active_mission or {}).get("type") == "auto_claim_guidance":
        needs.append(
            _response_need(
                key="auto_claim_guidance",
                label="orientacion sobre el siniestro automotor",
                confidence=0.62,
                source="active_mission",
                evidence=(conversation_state.active_mission or {}).get("goal"),
            )
        )
    if not needs:
        needs.append(
            _response_need(
                key="understand_user_need",
                label="comprender la necesidad del usuario",
                confidence=0.45,
                source="fallback",
                evidence=str(message),
            )
        )
    return _dedupe_needs(needs)


def _response_need(*, key: str, label: str, confidence: float, source: str, evidence: Any) -> Dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "confidence": round(float(confidence), 4),
        "source": source,
        "evidence": {"text": str(evidence or "")},
    }


def _conversational_intent_model(
    conversation_state: ConversationState,
    message: Any,
    normalized: str,
) -> Dict[str, Any]:
    explicit_questions = _explicit_questions_from_message(message, normalized)
    implicit_questions: list[Dict[str, Any]] = []
    user_assumptions: list[Dict[str, Any]] = []
    missing_information: list[Dict[str, Any]] = []
    matched_signals: list[str] = []

    if _mentions_vehicle_repair_need(normalized):
        matched_signals.append("vehicle_repair_need")
        if not explicit_questions:
            explicit_questions.append(
                _intent_question(
                    key="can_repair_vehicle",
                    text="Puedo arreglar el auto?",
                    source="inferred_from_repair_phrase",
                    evidence=normalized,
                    confidence=0.78,
                )
            )
        implicit_questions.append(
            _intent_question(
                key="repair_affects_claim",
                text="Arreglar el auto puede perjudicar la denuncia o evaluacion del siniestro?",
                source="pragmatic_repair_concern",
                evidence=normalized,
                confidence=0.86,
            )
        )
        user_assumptions.append(
            _intent_assumption(
                key="early_repair_may_affect_claim",
                text="El usuario supone que reparar antes de una autorizacion podria afectar el tramite.",
                evidence=normalized,
                confidence=0.74,
            )
        )
        missing_information.extend(
            [
                _intent_missing_information(
                    key="claim_authorization_status",
                    label="estado de autorizacion o indicacion de la aseguradora",
                    purpose="definir si reparar ahora puede afectar la evaluacion",
                ),
                _intent_missing_information(
                    key="damage_evidence_available",
                    label="fotos, presupuesto o respaldo del dano",
                    purpose="preservar evidencia antes de reparar",
                ),
            ]
        )

    if _mentions_contact_timing_need(normalized):
        matched_signals.append("contact_timing_need")
        implicit_questions.append(
            _intent_question(
                key="case_following_process",
                text="Mi caso sigue correctamente el proceso o quedo trabado?",
                source="pragmatic_contact_timing_concern",
                evidence=normalized,
                confidence=0.84,
            )
        )
        user_assumptions.append(
            _intent_assumption(
                key="lack_of_contact_may_indicate_problem",
                text="El usuario supone que si no lo contactan puede haber un problema con el tramite.",
                evidence=normalized,
                confidence=0.72,
            )
        )
        missing_information.extend(
            [
                _intent_missing_information(
                    key="claim_report_loaded",
                    label="si la denuncia esta cargada",
                    purpose="verificar si el caso inicio el circuito esperado",
                ),
                _intent_missing_information(
                    key="documentation_complete",
                    label="si la documentacion quedo completa",
                    purpose="identificar bloqueos posibles antes del contacto",
                ),
            ]
        )

    if _mentions_no_photo_request(normalized):
        matched_signals.append("no_photo_request")
        implicit_questions.append(
            _intent_question(
                key="missed_required_step",
                text="Hice algo mal o me falto cargar fotos?",
                source="pragmatic_missing_photo_request_concern",
                evidence=normalized,
                confidence=0.87,
            )
        )
        user_assumptions.append(
            _intent_assumption(
                key="photos_should_have_been_requested",
                text="El usuario supone que las fotos siempre deberian ser solicitadas.",
                evidence=normalized,
                confidence=0.78,
            )
        )
        missing_information.extend(
            [
                _intent_missing_information(
                    key="claim_type",
                    label="tipo de siniestro",
                    purpose="saber si las fotos son obligatorias en ese circuito",
                ),
                _intent_missing_information(
                    key="channel_checklist",
                    label="checklist o estado mostrado por el canal",
                    purpose="confirmar si aparece alguna observacion pendiente",
                ),
            ]
        )

    if _mentions_photo_upload_need(normalized) and not _mentions_no_photo_request(normalized):
        matched_signals.append("photo_upload_need")
        implicit_questions.append(
            _intent_question(
                key="photos_loaded_correctly",
                text="Las fotos quedaron cargadas correctamente?",
                source="photo_upload_uncertainty",
                evidence=normalized,
                confidence=0.78,
            )
        )

    if not explicit_questions and not implicit_questions:
        if _is_ambiguous_reference(normalized):
            matched_signals.append("ambiguous_reference")
            missing_information.append(
                _intent_missing_information(
                    key="reference_target",
                    label="a que se refiere el usuario",
                    purpose="evitar inferir una preocupacion sin evidencia suficiente",
                )
            )
        else:
            matched_signals.append("literal_need_only")

    dominant_concern = _intent_dominant_concern(
        normalized=normalized,
        explicit_questions=explicit_questions,
        implicit_questions=implicit_questions,
        matched_signals=matched_signals,
    )
    user_goal = _intent_user_goal(dominant_concern)
    response_objective = _intent_response_objective(dominant_concern)
    return {
        "contract": "conversational_intent_model.v1",
        "explicit_questions": explicit_questions,
        "implicit_questions": implicit_questions,
        "dominant_concern": dominant_concern,
        "user_goal": user_goal,
        "user_assumptions": user_assumptions,
        "missing_information": _dedupe_intent_items(missing_information),
        "response_objective": response_objective,
        "evidence": {
            "message": str(message),
            "normalized_message": normalized,
            "matched_signals": matched_signals,
            "active_mission_type": (conversation_state.active_mission or {}).get("type"),
            "active_topic": deepcopy(_active_topic_from_stack(conversation_state.topic_stack) or {}),
        },
        "component": "conversation_state",
        "turn": int(conversation_state.turn_count),
    }


def _explicit_questions_from_message(message: Any, normalized: str) -> list[Dict[str, Any]]:
    questions: list[Dict[str, Any]] = []
    if "?" in str(message) or normalized.startswith(("puedo ", "cuando ", "cuanto ", "que ", "como ", "donde ")):
        if _mentions_vehicle_repair_need(normalized):
            questions.append(
                _intent_question(
                    key="can_repair_vehicle",
                    text="Puedo arreglar el auto?",
                    source="explicit_question",
                    evidence=str(message),
                    confidence=0.9,
                )
            )
        if _mentions_contact_timing_need(normalized):
            questions.append(
                _intent_question(
                    key="when_will_contact_me",
                    text="Cuando me van a contactar?",
                    source="explicit_question",
                    evidence=str(message),
                    confidence=0.88,
                )
            )
        if _mentions_photo_upload_need(normalized) and not _mentions_no_photo_request(normalized):
            questions.append(
                _intent_question(
                    key="were_photos_sent",
                    text="Las fotos fueron enviadas o cargadas?",
                    source="explicit_question",
                    evidence=str(message),
                    confidence=0.82,
                )
            )
    if _mentions_no_photo_request(normalized):
        questions.append(
            _intent_question(
                key="photos_not_requested",
                text="No me pidieron las fotos.",
                source="explicit_statement",
                evidence=str(message),
                confidence=0.76,
            )
        )
    return _dedupe_intent_items(questions)


def _intent_question(*, key: str, text: str, source: str, evidence: str, confidence: float) -> Dict[str, Any]:
    return {
        "key": key,
        "text": text,
        "source": source,
        "confidence": round(float(confidence), 4),
        "evidence": {"text": evidence},
    }


def _intent_assumption(*, key: str, text: str, evidence: str, confidence: float) -> Dict[str, Any]:
    return {
        "key": key,
        "text": text,
        "confidence": round(float(confidence), 4),
        "evidence": {"text": evidence},
    }


def _intent_missing_information(*, key: str, label: str, purpose: str) -> Dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "purpose": purpose,
    }


def _intent_dominant_concern(
    *,
    normalized: str,
    explicit_questions: Sequence[Mapping[str, Any]],
    implicit_questions: Sequence[Mapping[str, Any]],
    matched_signals: Sequence[str],
) -> Dict[str, Any]:
    if "vehicle_repair_need" in matched_signals:
        return {
            "key": "preserve_claim_while_repairing_vehicle",
            "need_key": "vehicle_repair_authorization",
            "label": "necesita arreglar el auto sin perjudicar el tramite",
            "confidence": 0.88,
            "source": "implicit_question",
            "evidence": {"explicit": [dict(item) for item in explicit_questions], "implicit": [dict(item) for item in implicit_questions]},
        }
    if "contact_timing_need" in matched_signals:
        return {
            "key": "case_may_not_be_progressing",
            "need_key": "claim_contact_progress",
            "label": "quiere saber si su caso sigue el proceso esperado",
            "confidence": 0.84,
            "source": "implicit_question",
            "evidence": {"implicit": [dict(item) for item in implicit_questions]},
        }
    if "no_photo_request" in matched_signals:
        return {
            "key": "missed_photo_step",
            "need_key": "photo_requirement_confidence",
            "label": "quiere saber si hizo algo mal al no cargar fotos",
            "confidence": 0.86,
            "source": "implicit_question",
            "evidence": {"implicit": [dict(item) for item in implicit_questions]},
        }
    if "ambiguous_reference" in matched_signals:
        return {
            "key": "ambiguous_reference",
            "need_key": "understand_user_need",
            "label": "referencia conversacional insuficiente",
            "confidence": 0.42,
            "source": "missing_reference",
            "evidence": {"normalized_message": normalized},
        }
    if explicit_questions:
        first = dict(explicit_questions[0])
        return {
            "key": first.get("key"),
            "need_key": first.get("key"),
            "label": first.get("text"),
            "confidence": first.get("confidence", 0.5),
            "source": "explicit_question",
            "evidence": first.get("evidence", {}),
        }
    return {
        "key": "literal_need",
        "need_key": "",
        "label": "necesidad literal del turno",
        "confidence": 0.4,
        "source": "fallback",
        "evidence": {"normalized_message": normalized},
    }


def _intent_user_goal(dominant_concern: Mapping[str, Any]) -> Dict[str, Any]:
    key = str(dominant_concern.get("key") or "")
    goals = {
        "preserve_claim_while_repairing_vehicle": "reparar o usar el vehiculo sin afectar el reclamo",
        "case_may_not_be_progressing": "entender si el tramite avanza normalmente y que revisar",
        "missed_photo_step": "confirmar si falta una accion propia y como corregirla",
        "ambiguous_reference": "aclarar a que se refiere antes de responder",
    }
    return {
        "key": key or "unknown",
        "label": goals.get(key, str(dominant_concern.get("label") or "resolver la consulta")),
        "source": dominant_concern.get("source"),
        "confidence": dominant_concern.get("confidence"),
    }


def _intent_response_objective(dominant_concern: Mapping[str, Any]) -> Dict[str, Any]:
    key = str(dominant_concern.get("key") or "")
    need_key = str(dominant_concern.get("need_key") or "")
    objectives = {
        "preserve_claim_while_repairing_vehicle": "reducir incertidumbre sobre reparar el auto y explicar como preservar evidencia",
        "case_may_not_be_progressing": "explicar que revisar para saber si el caso sigue el proceso esperado",
        "missed_photo_step": "tranquilizar sin asumir error y explicar como verificar si las fotos son necesarias",
        "ambiguous_reference": "pedir aclaracion minima antes de inferir",
    }
    return {
        "key": key or "literal_response",
        "need_key": need_key,
        "label": objectives.get(key, str(dominant_concern.get("label") or "responder la consulta")),
        "confidence": dominant_concern.get("confidence", 0.5),
        "evidence": deepcopy(dict(dominant_concern.get("evidence") or {})),
    }


def _dedupe_intent_items(items: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    for item in items:
        key = str(item.get("key") or "")
        if not key:
            continue
        existing = by_key.get(key)
        if existing is None or float(item.get("confidence") or 0.0) > float(existing.get("confidence") or 0.0):
            by_key[key] = deepcopy(dict(item))
    return list(by_key.values())


def _intent_model_from_state(conversation_state: ConversationState) -> Dict[str, Any]:
    trace = conversation_state.derived_state.get("conversation_intent_model")
    if isinstance(trace, Mapping):
        model = trace.get("model")
        if isinstance(model, Mapping):
            return deepcopy(dict(model))
        return deepcopy(dict(trace))
    return {}


def _dedupe_needs(needs: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    for need in needs:
        key = str(need.get("key") or "")
        if not key:
            continue
        existing = by_key.get(key)
        if existing is None or float(need.get("confidence") or 0.0) > float(existing.get("confidence") or 0.0):
            by_key[key] = deepcopy(dict(need))
    return sorted(by_key.values(), key=lambda item: float(item.get("confidence") or 0.0), reverse=True)


def _dominant_concern_from_needs(
    normalized: str,
    needs: Sequence[Mapping[str, Any]],
    intent_model: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    model_concern = dict((intent_model or {}).get("dominant_concern") or {})
    model_need_key = str(model_concern.get("need_key") or "")
    if model_need_key:
        for need in needs:
            if need.get("key") == model_need_key:
                return {
                    "key": model_need_key,
                    "label": model_concern.get("label") or need.get("label"),
                    "confidence": max(float(model_concern.get("confidence") or 0.0), float(need.get("confidence") or 0.0)),
                    "source": "conversation_intent_model",
                    "implicit_concern": deepcopy(model_concern),
                }
    explicit_concern = any(
        phrase in normalized
        for phrase in (
            "lo que mas me preocupa",
            "lo que más me preocupa",
            "me preocupa",
            "mi preocupacion",
            "mi preocupación",
            "lo principal",
            "mi duda principal",
        )
    )
    if explicit_concern:
        concern_need = _need_for_dominant_clause(normalized, needs) or (dict(needs[0]) if needs else {})
        return {
            "key": concern_need.get("key", "explicit_user_concern"),
            "label": concern_need.get("label", "preocupacion expresada por el usuario"),
            "confidence": max(float(concern_need.get("confidence") or 0.0), 0.88),
            "source": "explicit_concern_marker",
        }
    if needs:
        first = dict(needs[0])
        return {
            "key": first.get("key"),
            "label": first.get("label"),
            "confidence": float(first.get("confidence") or 0.0),
            "source": first.get("source"),
        }
    return {"key": "unknown", "label": "sin preocupacion dominante detectada", "confidence": 0.0, "source": "none"}


def _need_for_dominant_clause(normalized: str, needs: Sequence[Mapping[str, Any]]) -> Dict[str, Any] | None:
    markers = ("lo que mas me preocupa", "lo que más me preocupa", "me preocupa", "mi duda principal", "lo principal")
    marker_index = min((normalized.find(marker) for marker in markers if marker in normalized), default=-1)
    dominant_clause = normalized[marker_index:] if marker_index >= 0 else normalized
    for need in needs:
        key = str(need.get("key") or "")
        if key == "vehicle_repair_authorization" and _mentions_vehicle_repair_need(dominant_clause):
            return dict(need)
        if key == "photo_upload_status" and _mentions_photo_upload_need(dominant_clause):
            return dict(need)
        if key == "claim_report_status" and _mentions_claim_report_need(dominant_clause):
            return dict(need)
        if key == "documentation_guidance" and _mentions_documentation_need(dominant_clause):
            return dict(need)
    return None


def _primary_need_from(
    needs: Sequence[Mapping[str, Any]],
    dominant_concern: Mapping[str, Any],
    conversation_state: ConversationState,
) -> Dict[str, Any]:
    concern_key = str(dominant_concern.get("key") or "")
    for need in needs:
        if need.get("key") == concern_key:
            primary = deepcopy(dict(need))
            primary["selected_reason"] = "dominant_concern"
            return primary
    if needs:
        primary = deepcopy(dict(needs[0]))
        primary["selected_reason"] = "highest_confidence_need"
        return primary
    if conversation_state.pending_questions:
        question = dict(conversation_state.pending_questions[0])
        return _response_need(
            key=f"answer_pending_{question.get('slot')}",
            label=str(question.get("reason") or question.get("slot") or "resolver pregunta pendiente"),
            confidence=0.55,
            source="pending_question",
            evidence=question.get("prompt"),
        )
    return _response_need(
        key="understand_user_need",
        label="comprender la necesidad del usuario",
        confidence=0.4,
        source="fallback",
        evidence="",
    )


def _required_information_for_response(
    conversation_state: ConversationState,
    primary_need: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    required: list[Dict[str, Any]] = []
    for question in sorted(conversation_state.pending_questions, key=lambda item: int(item.get("priority", 100) or 100)):
        slot = str(question.get("slot") or "")
        if not slot:
            continue
        if slot == "user_need" and primary_need.get("key") != "understand_user_need":
            continue
        required.append(
            {
                "slot": slot,
                "question": _justified_question_for_slot(slot),
                "purpose": _question_purpose_for_slot(slot, primary_need),
                "needed_for": _question_needed_for_slot(slot),
                "priority": int(question.get("priority", _slot_priority(slot)) or _slot_priority(slot)),
                "source_question": deepcopy(dict(question)),
            }
        )
    mission = conversation_state.active_mission or {}
    fact_values = _active_fact_values(conversation_state.confirmed_facts)
    next_act = str(mission.get("next_act") or "")
    existing_slots = {str(item.get("slot")) for item in required}
    if next_act == "check_claim_report_loaded" and fact_values.get("claim_report_loaded") is None and "claim_report_loaded" not in existing_slots:
        required.append(
            {
                "slot": "claim_report_loaded",
                "question": _justified_question_for_slot("claim_report_loaded"),
                "purpose": _question_purpose_for_slot("claim_report_loaded", primary_need),
                "needed_for": _question_needed_for_slot("claim_report_loaded"),
                "priority": 30,
                "source_question": {
                    "source": "mission_next_act",
                    "next_act": next_act,
                },
            }
        )
    if next_act == "check_documentation_available" and fact_values.get("documentation_available") is None and "documentation_available" not in existing_slots:
        required.append(
            {
                "slot": "documentation_available",
                "question": _justified_question_for_slot("documentation_available"),
                "purpose": _question_purpose_for_slot("documentation_available", primary_need),
                "needed_for": _question_needed_for_slot("documentation_available"),
                "priority": 35,
                "source_question": {
                    "source": "mission_next_act",
                    "next_act": next_act,
                },
            }
        )
    if not required and primary_need.get("key") == "photo_upload_status":
        required.append(
            {
                "slot": "photo_upload_evidence",
                "question": "Podes revisar si la carga figura como enviada o mandarme una captura del estado?",
                "purpose": "verificar si las fotos quedaron cargadas y si aparece alguna observacion",
                "needed_for": "photo_upload_status",
                "priority": 40,
                "source_question": {},
            }
        )
    return required


def _justified_question_for_slot(slot: str) -> str:
    return {
        "injuries": "Hubo lesionados?",
        "user_role": "Sos asegurado de Galicia o tercero damnificado?",
        "claim_report_loaded": "La denuncia ya esta cargada?",
        "documentation_available": "Tenes toda la documentacion?",
        "user_need": "Que necesitas resolver primero?",
    }.get(slot, f"Me confirmas {slot}?")


def _question_purpose_for_slot(slot: str, primary_need: Mapping[str, Any]) -> str:
    if slot == "injuries":
        return "definir si corresponde priorizar asistencia o derivacion antes del tramite"
    if slot == "user_role":
        return "orientarte por el circuito que corresponde a tu rol"
    if slot == "claim_report_loaded":
        return "saber si corresponde completar la carga o revisar documentacion"
    if slot == "documentation_available":
        return "ver si corresponde seguimiento o preparar el resumen del tramite"
    if slot == "user_need":
        return "responder primero la preocupacion mas importante"
    if primary_need.get("key") == "vehicle_repair_authorization":
        return "evitar indicarte un paso que pueda afectar la evaluacion del arreglo"
    return "elegir el siguiente paso sin inventar datos"


def _question_needed_for_slot(slot: str) -> str:
    return {
        "injuries": "safety_and_escalation_path",
        "user_role": "claim_guidance_path",
        "claim_report_loaded": "claim_report_or_documentation_path",
        "documentation_available": "claim_follow_up_path",
        "user_need": "response_prioritization",
    }.get(slot, "next_action_selection")


def _response_priority_for(
    *,
    primary_need: Mapping[str, Any],
    secondary_needs: Sequence[Mapping[str, Any]],
    required_information: Sequence[Mapping[str, Any]],
) -> list[str]:
    priority = [str(primary_need.get("key") or "primary_need")]
    priority.extend(str(need.get("key")) for need in secondary_needs if need.get("key"))
    if required_information:
        priority.append("required_information")
    priority.append("next_action")
    return priority


def _response_next_action(
    *,
    conversation_state: ConversationState,
    primary_need: Mapping[str, Any],
    required_information: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    if primary_need.get("key") == "vehicle_repair_authorization":
        return {
            "type": "answer_then_collect_context",
            "label": "responder sobre arreglo del auto y luego pedir el dato necesario",
            "mission_next_act": (conversation_state.active_mission or {}).get("next_act"),
        }
    if required_information:
        return {
            "type": "ask_justified_question",
            "label": required_information[0].get("question"),
            "mission_next_act": (conversation_state.active_mission or {}).get("next_act"),
        }
    return {
        "type": "answer",
        "label": "responder la necesidad principal",
        "mission_next_act": (conversation_state.active_mission or {}).get("next_act"),
    }


def _unresolved_questions_for_response(
    needs: Sequence[Mapping[str, Any]],
    required_information: Sequence[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    unresolved = [
        {
            "type": "required_information",
            "slot": item.get("slot"),
            "question": item.get("question"),
            "purpose": item.get("purpose"),
        }
        for item in required_information
    ]
    for need in needs:
        if need.get("key") == "photo_upload_status":
            unresolved.append(
                {
                    "type": "secondary_need",
                    "need": "photo_upload_status",
                    "question": "confirmar si las fotos quedaron cargadas",
                }
            )
    return unresolved


def _mentions_vehicle_repair_need(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "arreglar el auto",
            "arreglar mi auto",
            "reparar el auto",
            "reparar mi auto",
            "puedo arreglar",
            "puedo reparar",
            "mandarlo al taller",
            "llevarlo al taller",
            "arreglo del auto",
            "si arreglo el auto",
            "arreglo el auto antes",
            "antes de que me autoricen",
            "antes de tener autorizacion",
        )
    )


def _mentions_photo_upload_need(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "mande las fotos",
            "mandé las fotos",
            "envie las fotos",
            "envié las fotos",
            "subi las fotos",
            "subí las fotos",
            "cargue las fotos",
            "cargué las fotos",
            "subir fotos",
            "las fotos",
            "fotos",
        )
    )


def _mentions_no_photo_request(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "no me pidieron las fotos",
            "no pidieron las fotos",
            "nunca me pidieron fotos",
            "no me solicitaron las fotos",
            "no me aparece cargar fotos",
        )
    )


def _mentions_contact_timing_need(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "cuando me van a contactar",
            "cuándo me van a contactar",
            "cuanto suele tardar",
            "cuanto tarda normalmente",
            "cuanto tarda",
            "cuanto demora",
            "cuando me contactan",
            "cuándo me contactan",
            "cuando me llaman",
            "cuándo me llaman",
            "nadie me contacto",
            "nadie me contactó",
            "no me contactaron",
            "no me llamaron",
        )
    )


def _mentions_claim_report_need(normalized: str) -> bool:
    return "denuncia" in normalized or "siniestro cargado" in normalized or "tramite cargado" in normalized


def _mentions_documentation_need(normalized: str) -> bool:
    return "documentacion" in normalized or "documentación" in normalized or "documentos" in normalized


def _mentions_status_or_payment_need(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "estado del siniestro",
            "estado de mi siniestro",
            "cuando me pagan",
            "cuanto suele tardar",
            "cuanto tarda normalmente",
            "cuanto tardan",
            "cuanto tarda",
            "cuanto demora",
            "cuanto demoran",
            "plazo",
            "plazos",
            "novedades",
            "aprobaron",
            "rechazaron",
        )
    )


def _is_ambiguous_reference(normalized: str) -> bool:
    return normalized.strip(" .!?") in {
        "eso esta bien",
        "eso esta bien?",
        "y eso",
        "eso",
        "esta bien",
        "esta bien?",
        "lo anterior",
    }


def update_topic_stack(
    conversation_state: ConversationState,
    message: Any,
) -> tuple[ConversationState, Dict[str, Any]]:
    normalized = normalize_text(message)
    stack = [_normalize_topic(topic) for topic in conversation_state.topic_stack if isinstance(topic, Mapping)]
    stack = [topic for topic in stack if topic]
    active_before = _active_topic_from_stack(stack)
    act = str((conversation_state.last_conversational_act or {}).get("act") or ConversationalActType.UNKNOWN)
    direction = _topic_navigation_direction(normalized, conversation_state.last_conversational_act)
    current_topic = (
        None
        if active_before
        and _topic_is_unresolved_other(active_before)
        and act not in {ConversationalActType.CONTINUATION, ConversationalActType.TOPIC_SHIFT, ConversationalActType.NEW_INFORMATION}
        else _topic_from_current_state(conversation_state, message)
    )
    transition_type = ""
    reason = ""
    suspended_topic: Dict[str, Any] | None = None
    resumed_topic: Dict[str, Any] | None = None
    ambiguity: Dict[str, Any] | None = None

    if act == ConversationalActType.TOPIC_SHIFT and direction == "new_topic":
        if active_before:
            stack = _replace_topic(stack, _topic_with_status(active_before, TopicStatus.SUSPENDED, conversation_state.turn_count))
            suspended_topic = _topic_with_status(active_before, TopicStatus.SUSPENDED, conversation_state.turn_count)
        new_topic = _new_unresolved_topic(conversation_state, message)
        stack = _remove_topic(stack, str(new_topic["id"]))
        stack.append(new_topic)
        transition_type = "topic_switched"
        reason = "user_requested_new_topic"
    elif act == ConversationalActType.TOPIC_SHIFT and direction in {"resume_previous", "indirect_previous"}:
        match, match_reason, ambiguity = _resolve_topic_reference(stack, normalized, conversation_state)
        if match:
            if active_before and active_before.get("id") != match.get("id"):
                stack = _replace_topic(stack, _topic_with_status(active_before, TopicStatus.SUSPENDED, conversation_state.turn_count))
                suspended_topic = _topic_with_status(active_before, TopicStatus.SUSPENDED, conversation_state.turn_count)
            resumed_topic = _topic_with_status(
                _topic_refreshed_from_state(match, conversation_state),
                TopicStatus.RESUMED,
                conversation_state.turn_count,
            )
            stack = _remove_topic(stack, str(resumed_topic["id"]))
            stack.append(resumed_topic)
            transition_type = "topic_resumed"
            reason = match_reason
        elif ambiguity:
            transition_type = "topic_reference_ambiguous"
            reason = "insufficient_evidence_to_resume_topic"
    elif act == ConversationalActType.CONTINUATION:
        if active_before and _topic_is_unresolved_other(active_before):
            match, match_reason, ambiguity = _resolve_topic_reference(stack, normalized, conversation_state)
            if match:
                stack = _replace_topic(stack, _topic_with_status(active_before, TopicStatus.SUSPENDED, conversation_state.turn_count))
                suspended_topic = _topic_with_status(active_before, TopicStatus.SUSPENDED, conversation_state.turn_count)
                resumed_topic = _topic_with_status(
                    _topic_refreshed_from_state(match, conversation_state),
                    TopicStatus.RESUMED,
                    conversation_state.turn_count,
                )
                stack = _remove_topic(stack, str(resumed_topic["id"]))
                stack.append(resumed_topic)
                transition_type = "topic_resumed"
                reason = match_reason
            elif ambiguity:
                transition_type = "topic_reference_ambiguous"
                reason = "continuation_has_multiple_suspended_candidates"
        elif active_before:
            refreshed = _topic_refreshed_from_state(active_before, conversation_state)
            stack = _replace_topic(stack, _topic_with_status(refreshed, TopicStatus.ACTIVE, conversation_state.turn_count))
            transition_type = "topic_continued"
            reason = "user_requested_continuation"
        elif current_topic:
            stack.append(current_topic)
            transition_type = "topic_created"
            reason = "continuation_started_available_focus"
    elif current_topic:
        existing = _find_topic_by_id(stack, str(current_topic["id"]))
        if existing:
            updated = _topic_refreshed_from_state(existing, conversation_state)
            if active_before and active_before.get("id") != updated.get("id"):
                stack = _replace_topic(stack, _topic_with_status(active_before, TopicStatus.SUSPENDED, conversation_state.turn_count))
                suspended_topic = _topic_with_status(active_before, TopicStatus.SUSPENDED, conversation_state.turn_count)
            stack = _remove_topic(stack, str(updated["id"]))
            stack.append(_topic_with_status(updated, TopicStatus.ACTIVE, conversation_state.turn_count))
            transition_type = "topic_updated" if active_before else "topic_created"
            reason = "current_focus_updated"
        else:
            if active_before:
                stack = _replace_topic(stack, _topic_with_status(active_before, TopicStatus.SUSPENDED, conversation_state.turn_count))
                suspended_topic = _topic_with_status(active_before, TopicStatus.SUSPENDED, conversation_state.turn_count)
            stack.append(current_topic)
            transition_type = "topic_created"
            reason = "current_focus_created"

    if not transition_type:
        return conversation_state, {}

    active_after = _active_topic_from_stack(stack)
    trace = {
        "contract": "topic_stack_transition.v1",
        "component": "conversation_state",
        "message": str(message),
        "act": act,
        "direction": direction,
        "transition": {
            "type": transition_type,
            "reason": reason,
            "from_topic_id": active_before.get("id") if active_before else None,
            "to_topic_id": active_after.get("id") if active_after else None,
        },
        "active_topic": deepcopy(active_after or {}),
        "topic_suspended": deepcopy(suspended_topic or {}),
        "topic_resumed": deepcopy(resumed_topic or {}),
        "ambiguity": deepcopy(ambiguity or {}),
        "summary_updated": deepcopy((active_after or {}).get("summary")),
        "topics": deepcopy(stack),
    }
    derived_state = deepcopy(conversation_state.derived_state)
    derived_state["topic_stack"] = trace
    mission_proposal = _topic_shift_mission_proposal(
        conversation_state=conversation_state,
        suspended_topic=suspended_topic,
        resumed_topic=resumed_topic,
        turn=conversation_state.turn_count,
    )
    if mission_proposal:
        derived_state["mission_transition_proposals"] = [
            *(derived_state.get("mission_transition_proposals") or []),
            mission_proposal,
        ]
    focus = _focus_from_active_topic(active_after, fallback=conversation_state.focus)
    return (
        replace(
            conversation_state,
            focus=focus,
            topic_stack=stack,
            derived_state=derived_state,
            projection_sources=_append_unique(
                conversation_state.projection_sources,
                "conversation_state.topic_stack",
            ),
        ),
        trace,
    )


def _topic_shift_mission_proposal(
    *,
    conversation_state: "ConversationState",
    suspended_topic: Mapping[str, Any] | None,
    resumed_topic: Mapping[str, Any] | None,
    turn: int,
) -> Dict[str, Any] | None:
    """ACA-305C reverse cross-transition matrix: a topic suspend/resume event
    for a mission-backed topic must, in the same turn, propose the matching
    mission transition -- closing the divergence ACA-305C section 1.3
    evidenced (topic resume today never resumes the mission). This proposes;
    it never writes `active_mission` (ACA-305B section 8)."""

    mission = conversation_state.active_mission
    if not mission or not mission.get("type"):
        return None
    mission_topic_id = f"mission:{mission.get('type')}"
    act = dict(conversation_state.last_conversational_act or {})
    confidence = float(act.get("confidence") or 0.0)

    if resumed_topic and str(resumed_topic.get("id") or "") == mission_topic_id:
        if str(mission.get("lifecycle_status") or "") != MissionLifecycleStatus.SUSPENDED:
            return None
        target_status = (
            MissionLifecycleStatus.WAITING_USER
            if mission.get("missing")
            else MissionLifecycleStatus.GATHERING_INFORMATION
        )
        transition_type = "resume"
        delta = {"lifecycle_status": target_status, "status": _legacy_mission_status(target_status)}
        reason = "topic_resumed"
        topic_effect = {
            "topic_id": mission_topic_id,
            "from_status": TopicStatus.SUSPENDED,
            "to_status": resumed_topic.get("status"),
            "reason": "mirrors_mission_transition:resume",
        }
    elif suspended_topic and str(suspended_topic.get("id") or "") == mission_topic_id:
        if str(mission.get("lifecycle_status") or "") == MissionLifecycleStatus.SUSPENDED:
            return None
        transition_type = "suspend"
        delta = {"lifecycle_status": MissionLifecycleStatus.SUSPENDED, "status": "suspended"}
        reason = "topic_suspended"
        topic_effect = {
            "topic_id": mission_topic_id,
            "from_status": TopicStatus.ACTIVE,
            "to_status": suspended_topic.get("status"),
            "reason": "mirrors_mission_transition:suspend",
        }
    else:
        return None

    return {
        "contract": MISSION_TRANSITION_PROPOSAL_CONTRACT,
        "proposal_id": f"topic_shift:{int(turn)}:{transition_type}:{mission.get('type')}",
        "component": "conversation_state",
        "turn": int(turn),
        "transition_type": transition_type,
        "target_mission_type": None,
        "mission_before": deepcopy(mission),
        "mission_delta": delta,
        "evidence": {"evidence_kind": "conversational_act", "act": deepcopy(act)},
        "confidence": confidence,
        "reason": reason,
        "topic_effect": topic_effect,
    }


def evaluate_conversational_goal_fulfillment(
    conversation_state: ConversationState,
    response: Any,
) -> tuple[ConversationState, Dict[str, Any]]:
    trace = deepcopy(dict(conversation_state.derived_state.get("conversation_goal") or {}))
    goal = deepcopy(dict(trace.get("goal") or {}))
    if not goal:
        return conversation_state, {}
    fulfillment = _evaluate_goal_fulfillment(goal, str(response or ""))
    goal["fulfillment"] = fulfillment
    trace["goal"] = goal
    trace["fulfillment"] = fulfillment
    derived_state = deepcopy(conversation_state.derived_state)
    derived_state["conversation_goal"] = trace
    return replace(conversation_state, derived_state=derived_state), fulfillment


def evaluate_conversation_fulfillment(
    conversation_state: ConversationState,
    response: Any,
) -> tuple[ConversationState, Dict[str, Any]]:
    fulfillment = _conversation_fulfillment(conversation_state, str(response or ""))
    if not fulfillment:
        return conversation_state, {}
    trace = {
        "contract": "conversation_fulfillment_trace.v1",
        "component": "conversation_state",
        "fulfillment": deepcopy(fulfillment),
        "fulfilled_goal": deepcopy(fulfillment.get("fulfilled_goal") or {}),
        "fulfilled_steps": deepcopy(fulfillment.get("fulfilled_steps") or []),
        "pending_steps": deepcopy(fulfillment.get("pending_steps") or []),
        "failed_steps": deepcopy(fulfillment.get("failed_steps") or []),
        "recovery_actions": deepcopy(fulfillment.get("recovery_actions") or []),
        "fulfillment_confidence": fulfillment.get("fulfillment_confidence"),
        "completion_reason": fulfillment.get("completion_reason"),
    }
    derived_state = deepcopy(conversation_state.derived_state)
    derived_state["conversation_fulfillment"] = trace
    return (
        replace(
            conversation_state,
            derived_state=derived_state,
            projection_sources=_append_unique(
                conversation_state.projection_sources,
                "conversation_state.conversation_fulfillment",
            ),
        ),
        fulfillment,
    )


def _conversation_fulfillment(
    conversation_state: ConversationState,
    response: str,
) -> Dict[str, Any]:
    conversation_plan = _conversation_plan_from_state(conversation_state)
    response_plan = _response_plan_from_state(conversation_state)
    if not conversation_plan and not response_plan:
        return {}
    normalized_response = normalize_text(response)
    active_steps = _active_steps_from_previous_plan(conversation_plan)
    plan_pending_steps = [deepcopy(dict(step)) for step in conversation_plan.get("pending_steps") or [] if isinstance(step, Mapping)]
    response_fulfilled_steps = _response_fulfilled_steps(
        conversation_state=conversation_state,
        response_plan=response_plan,
        conversation_plan=conversation_plan,
        normalized_response=normalized_response,
    )
    failed_steps = _conversation_failed_steps(
        conversation_state=conversation_state,
        conversation_plan=conversation_plan,
        normalized_response=normalized_response,
    )
    pending_steps = _conversation_fulfillment_pending_steps(
        plan_pending_steps,
        fulfilled_steps=response_fulfilled_steps,
        failed_steps=failed_steps,
    )
    fulfilled_goal = _fulfilled_goal_for_response(
        response_plan=response_plan,
        conversation_plan=conversation_plan,
        fulfilled_steps=response_fulfilled_steps,
        pending_steps=pending_steps,
        failed_steps=failed_steps,
        normalized_response=normalized_response,
    )
    recovery_actions = _conversation_recovery_actions(
        fulfilled_goal=fulfilled_goal,
        pending_steps=pending_steps,
        failed_steps=failed_steps,
        response_plan=response_plan,
        conversation_plan=conversation_plan,
    )
    confidence = _fulfillment_confidence(
        fulfilled_goal=fulfilled_goal,
        fulfilled_steps=response_fulfilled_steps,
        pending_steps=pending_steps,
        failed_steps=failed_steps,
    )
    return {
        "contract": "conversation_fulfillment.v1",
        "fulfilled_goal": fulfilled_goal,
        "fulfilled_steps": response_fulfilled_steps,
        "pending_steps": pending_steps,
        "failed_steps": failed_steps,
        "recovery_actions": recovery_actions,
        "fulfillment_confidence": confidence,
        "completion_reason": _completion_reason(
            fulfilled_goal=fulfilled_goal,
            recovery_actions=recovery_actions,
            pending_steps=pending_steps,
            failed_steps=failed_steps,
        ),
        "evaluated_plan": deepcopy(conversation_plan),
        "evaluated_response_plan": deepcopy(response_plan),
        "evidence": {
            "response": response,
            "normalized_response": normalized_response,
            "active_steps": deepcopy(active_steps),
        },
        "component": "conversation_state",
        "turn": int(conversation_state.turn_count),
    }


def _response_plan_from_state(conversation_state: ConversationState) -> Dict[str, Any]:
    trace = conversation_state.derived_state.get("conversation_response_plan")
    if isinstance(trace, Mapping):
        plan = trace.get("plan")
        if isinstance(plan, Mapping):
            return deepcopy(dict(plan))
        return deepcopy(dict(trace))
    return {}


def _response_fulfilled_steps(
    *,
    conversation_state: ConversationState,
    response_plan: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
    normalized_response: str,
) -> list[Dict[str, Any]]:
    fulfilled: list[Dict[str, Any]] = []
    for step in conversation_plan.get("completed_steps") or []:
        if isinstance(step, Mapping):
            item = deepcopy(dict(step))
            item["fulfillment_source"] = "conversation_plan_completed"
            fulfilled.append(item)
    primary_need = dict(response_plan.get("primary_user_need") or {})
    primary_answered = _primary_need_answered(primary_need, normalized_response)
    if primary_answered:
        fulfilled.append(
            {
                "contract": "conversation_fulfillment_step.v1",
                "id": f"answer_primary_need:{primary_need.get('key') or 'unknown'}",
                "type": "response_objective",
                "status": "fulfilled",
                "label": primary_need.get("label") or primary_need.get("key"),
                "source": "conversation_response_plan",
            }
        )
        for step in conversation_plan.get("pending_steps") or []:
            if isinstance(step, Mapping) and step.get("id") == "understand_user_need":
                item = deepcopy(dict(step))
                item["status"] = "fulfilled"
                item["fulfillment_source"] = "primary_need_answered"
                fulfilled.append(item)
    for step in conversation_plan.get("inserted_steps") or []:
        if isinstance(step, Mapping) and _inserted_step_answered(step, normalized_response):
            item = deepcopy(dict(step))
            item["status"] = "fulfilled"
            item["fulfillment_source"] = "response_answered_inserted_step"
            fulfilled.append(item)
    for item in response_plan.get("required_information") or []:
        if not isinstance(item, Mapping):
            continue
        if _question_asked_in_response(item, normalized_response):
            fulfilled.append(
                {
                    "contract": "conversation_fulfillment_step.v1",
                    "id": f"ask_required_information:{item.get('slot')}",
                    "type": "question_delivery",
                    "status": "fulfilled",
                    "slot": item.get("slot"),
                    "question": item.get("question"),
                    "purpose": item.get("purpose"),
                    "source": "conversation_response_plan.required_information",
                }
            )
    return _dedupe_steps(fulfilled)


def _conversation_failed_steps(
    *,
    conversation_state: ConversationState,
    conversation_plan: Mapping[str, Any],
    normalized_response: str,
) -> list[Dict[str, Any]]:
    if not conversation_plan:
        return []
    if conversation_state.derived_state.get("slot_resolution") or conversation_state.derived_state.get("fact_assimilation"):
        return []
    previous_plan = conversation_plan.get("previous_plan")
    if not isinstance(previous_plan, Mapping):
        return []
    previous_current = dict((previous_plan.get("active_plan") or {}).get("current_step") or {})
    current_step = dict((conversation_plan.get("active_plan") or {}).get("current_step") or {})
    if not previous_current or not current_step:
        return []
    if previous_current.get("id") != current_step.get("id"):
        return []
    if str(current_step.get("type") or "") not in {"slot", "fact", "clarification"}:
        return []
    failed = deepcopy(current_step)
    failed["status"] = "failed"
    failed["reason"] = "user_turn_did_not_satisfy_expected_step"
    failed["evidence"] = {"normalized_response": normalized_response}
    return [failed]


def _conversation_fulfillment_pending_steps(
    pending_steps: Sequence[Mapping[str, Any]],
    *,
    fulfilled_steps: Sequence[Mapping[str, Any]],
    failed_steps: Sequence[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    fulfilled_ids = {str(step.get("id") or "") for step in fulfilled_steps}
    failed_ids = {str(step.get("id") or "") for step in failed_steps}
    pending = []
    for step in pending_steps:
        step_id = str(step.get("id") or "")
        if step_id in fulfilled_ids:
            continue
        if step_id in failed_ids:
            continue
        pending.append(deepcopy(dict(step)))
    return pending


def _fulfilled_goal_for_response(
    *,
    response_plan: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
    fulfilled_steps: Sequence[Mapping[str, Any]],
    pending_steps: Sequence[Mapping[str, Any]],
    failed_steps: Sequence[Mapping[str, Any]],
    normalized_response: str,
) -> Dict[str, Any]:
    primary_need = dict(response_plan.get("primary_user_need") or {})
    primary_answered = _primary_need_answered(primary_need, normalized_response)
    has_required_question = any(step.get("type") == "question_delivery" for step in fulfilled_steps)
    has_pending_main = any(step.get("type") != "side_question" for step in pending_steps)
    if failed_steps:
        status = "failed"
        satisfied = False
    elif not has_pending_main and (primary_answered or not primary_need):
        status = "fulfilled"
        satisfied = True
    elif primary_answered and any(step.get("type") == "side_question" for step in fulfilled_steps):
        status = "partially_fulfilled"
        satisfied = True
    elif primary_answered and not has_required_question:
        status = "fulfilled"
        satisfied = True
    elif has_required_question or fulfilled_steps:
        status = "partially_fulfilled"
        satisfied = True
    else:
        status = "not_fulfilled"
        satisfied = False
    return {
        "contract": "fulfilled_conversation_goal.v1",
        "status": status,
        "satisfied": satisfied,
        "primary_user_need": deepcopy(primary_need),
        "conversation_plan_replanning_reason": conversation_plan.get("replanning_reason"),
    }


def _conversation_recovery_actions(
    *,
    fulfilled_goal: Mapping[str, Any],
    pending_steps: Sequence[Mapping[str, Any]],
    failed_steps: Sequence[Mapping[str, Any]],
    response_plan: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    actions: list[Dict[str, Any]] = []
    if failed_steps:
        selected = dict((response_plan.get("information_gain_plan") or {}).get("selected_question") or {})
        actions.append(
            {
                "contract": "conversation_recovery_action.v1",
                "action": "reask_or_reformulate",
                "reason": "expected_step_not_answered",
                "target_step": deepcopy(dict(failed_steps[0])),
                "selected_question": selected,
            }
        )
        return actions
    if any(step.get("type") == "side_question" for step in conversation_plan.get("inserted_steps") or []):
        main_pending = [dict(step) for step in pending_steps if step.get("type") != "side_question"]
        if main_pending:
            actions.append(
                {
                    "contract": "conversation_recovery_action.v1",
                    "action": "resume_main_plan",
                    "reason": "lateral_question_answered",
                    "target_step": deepcopy(main_pending[0]),
                }
            )
    if pending_steps and not actions:
        actions.append(
            {
                "contract": "conversation_recovery_action.v1",
                "action": "continue_with_next_pending_step",
                "reason": "conversation_goal_partially_fulfilled",
                "target_step": deepcopy(dict(pending_steps[0])),
            }
        )
    if not pending_steps and not actions:
        actions.append(
            {
                "contract": "conversation_recovery_action.v1",
                "action": "close_objective",
                "reason": "conversation_goal_fulfilled",
            }
        )
    return actions


def _fulfillment_confidence(
    *,
    fulfilled_goal: Mapping[str, Any],
    fulfilled_steps: Sequence[Mapping[str, Any]],
    pending_steps: Sequence[Mapping[str, Any]],
    failed_steps: Sequence[Mapping[str, Any]],
) -> float:
    if failed_steps:
        return 0.34
    status = str(fulfilled_goal.get("status") or "")
    if status == "fulfilled":
        return 0.9
    if status == "partially_fulfilled":
        return 0.68 if pending_steps else 0.76
    if fulfilled_steps:
        return 0.56
    return 0.3


def _completion_reason(
    *,
    fulfilled_goal: Mapping[str, Any],
    recovery_actions: Sequence[Mapping[str, Any]],
    pending_steps: Sequence[Mapping[str, Any]],
    failed_steps: Sequence[Mapping[str, Any]],
) -> str:
    if failed_steps:
        return "expected_step_not_satisfied_recovery_selected"
    action = str((recovery_actions[0] if recovery_actions else {}).get("action") or "")
    if action == "resume_main_plan":
        return "lateral_question_fulfilled_main_plan_resumed"
    if action == "continue_with_next_pending_step":
        return "turn_partially_fulfilled_next_step_pending"
    if not pending_steps and fulfilled_goal.get("status") == "fulfilled":
        return "conversation_goal_fulfilled"
    return "conversation_fulfillment_evaluated"


def _primary_need_answered(primary_need: Mapping[str, Any], normalized_response: str) -> bool:
    key = str(primary_need.get("key") or "")
    if not key:
        return False
    if key == "claim_contact_progress":
        return "siguiendo el circuito esperado" in normalized_response or "canal muestra" in normalized_response
    if key == "claim_status_or_payment":
        return "sobre los tiempos" in normalized_response or "dependen del estado" in normalized_response
    if key == "vehicle_repair_authorization":
        return "arreglar el auto" in normalized_response and "evaluacion del siniestro" in normalized_response
    if key == "photo_requirement_confidence":
        return "no significa necesariamente" in normalized_response and "fotos" in normalized_response
    if key == "photo_upload_status":
        return "fotos" in normalized_response and ("cargadas" in normalized_response or "observacion" in normalized_response)
    if key == "claim_report_status":
        return "denuncia" in normalized_response
    if key in {"auto_claim_guidance", "understand_user_need"}:
        return bool(normalized_response.strip())
    return bool(normalized_response.strip())


def _inserted_step_answered(step: Mapping[str, Any], normalized_response: str) -> bool:
    step_id = str(step.get("id") or "")
    decision = str(step.get("decision") or "")
    if step_id == "answer_lateral_process_timing" or decision == "process_progress_confidence":
        return "sobre los tiempos" in normalized_response or "siguiendo el circuito esperado" in normalized_response
    if decision == "vehicle_repair_authorization":
        return "arreglar el auto" in normalized_response
    if decision in {"photo_upload_status", "photo_requirement_confidence"}:
        return "fotos" in normalized_response
    if decision == "focus_management":
        return "retomo" in normalized_response or "contame mas" in normalized_response
    return False


def _question_asked_in_response(item: Mapping[str, Any], normalized_response: str) -> bool:
    question = normalize_text(item.get("question") or "").strip(" .!?")
    if not question:
        return False
    response = normalized_response.strip(" .!?")
    return question in response


def recognize_conversational_act(
    conversation_state: ConversationState,
    message: Any,
) -> tuple[ConversationState, Dict[str, Any]]:
    normalized = normalize_text(message)
    candidates = _conversation_act_candidates(conversation_state, message, normalized)
    selected = _select_conversational_act(candidates)
    trace = {
        "contract": "conversation_act_recognition.v1",
        "component": "conversation_state",
        "message": str(message),
        "selected": deepcopy(selected),
        "candidates": [deepcopy(dict(candidate)) for candidate in candidates],
        "previous_act": deepcopy(conversation_state.last_conversational_act),
        "pending_questions": [deepcopy(dict(question)) for question in conversation_state.pending_questions],
    }
    derived_state = deepcopy(conversation_state.derived_state)
    derived_state["conversation_act"] = trace
    return (
        replace(
            conversation_state,
            last_conversational_act=selected,
            derived_state=derived_state,
            projection_sources=_append_unique(
                conversation_state.projection_sources,
                "conversation_state.conversational_act_recognition",
            ),
        ),
        selected,
    )


def _conversation_act_candidates(
    conversation_state: ConversationState,
    message: Any,
    normalized: str,
) -> list[Dict[str, Any]]:
    candidates: list[Dict[str, Any]] = []
    pending_slots = _ordered_pending_slot_names(conversation_state.slots, conversation_state.pending_questions)
    has_pending_question = bool(pending_slots)
    revisable_targets = _active_fact_targets_for_message(conversation_state, normalized)

    if _looks_like_correction(normalized, revisable_targets):
        ambiguous_withdrawal = _is_generic_withdrawal(normalized) and len(revisable_targets) != 1
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.CORRECTION,
                confidence=0.91 if revisable_targets and not ambiguous_withdrawal else 0.8 if ambiguous_withdrawal else 0.68,
                reason=(
                    "correction_target_ambiguous"
                    if ambiguous_withdrawal
                    else "correction_cue_with_revisable_fact"
                    if revisable_targets
                    else "correction_cue_without_clear_target"
                ),
                signals=["correction_cue"],
                target={"facts": revisable_targets},
                impact={
                    "fact_revision": True,
                    "mission_reevaluation": True,
                    "requires_clarification": ambiguous_withdrawal or not bool(revisable_targets),
                },
            )
        )

    if has_pending_question and _looks_like_pending_answer(normalized, pending_slots, conversation_state.pending_questions):
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.PENDING_ANSWER,
                confidence=0.9 if _is_minimal_affirmation_or_negation(normalized) else 0.82,
                reason="message_answers_pending_question",
                signals=["pending_question", "slot_answer"],
                target={"slots": pending_slots, "primary_slot": pending_slots[0]},
                impact={
                    "slot_resolution": True,
                    "intent_override": True,
                    "mission_reevaluation": True,
                },
            )
        )

    if _mentions_simplification_request(normalized):
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.SIMPLIFICATION_REQUEST,
                confidence=0.94,
                reason="user_requests_simpler_explanation",
                signals=["simplification"],
                impact={"response_style": "simpler", "preserve_mission": True, "intent_override": True},
            )
        )
    if _mentions_recap_request(normalized):
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.RECAP_REQUEST,
                confidence=0.92,
                reason="user_requests_recap",
                signals=["recap"],
                impact={"recap_requested": True, "preserve_mission": True, "intent_override": True},
            )
        )
    if _mentions_topic_shift(normalized):
        direction = _topic_navigation_direction(normalized)
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.TOPIC_SHIFT,
                confidence=0.88,
                reason="user_requests_topic_navigation",
                signals=["topic_shift"],
                target={"direction": direction},
                impact={
                    "topic_navigation": True,
                    "preserve_mission": direction != "new_topic",
                    "intent_override": True,
                },
            )
        )
    if _mentions_continuation(normalized):
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.CONTINUATION,
                confidence=0.86,
                reason="user_requests_continuation",
                signals=["continuation"],
                impact={"continue_mission": True, "intent_override": True},
            )
        )
    if _mentions_deepening_request(normalized):
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.DEEPENING_REQUEST,
                confidence=0.84,
                reason="user_requests_more_detail",
                signals=["deepening"],
                impact={"response_style": "more_detail", "preserve_mission": True, "intent_override": True},
            )
        )
    if _mentions_clarification_request(normalized):
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.CLARIFICATION_REQUEST,
                confidence=0.82,
                reason="user_requests_clarification",
                signals=["clarification_request"],
                impact={"clarification_requested": True, "preserve_mission": True, "intent_override": True},
            )
        )
    if _mentions_closing(normalized):
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.CLOSING,
                confidence=0.82,
                reason="user_closes_or_thanks",
                signals=["closing"],
                impact={"close_or_pause": True},
            )
        )

    if _is_affirmation(normalized):
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.CONFIRMATION,
                confidence=0.76 if not has_pending_question else 0.48,
                reason="minimal_affirmation",
                signals=["affirmation"],
                impact={"may_confirm_previous_act": True, "intent_override": False},
            )
        )
    if _is_negation(normalized):
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.NEGATION,
                confidence=0.76 if not has_pending_question else 0.48,
                reason="minimal_negation",
                signals=["negation"],
                impact={"may_deny_previous_act": True, "intent_override": False},
            )
        )

    if not candidates and normalized:
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.NEW_INFORMATION,
                confidence=0.52,
                reason="content_turn_without_conversation_control_signal",
                signals=["content"],
                impact={"normal_pipeline": True},
            )
        )
    if not candidates:
        candidates.append(
            _conversational_act_candidate(
                conversation_state,
                message,
                normalized,
                act=ConversationalActType.UNKNOWN,
                confidence=0.0,
                reason="empty_or_unclassified_turn",
                signals=[],
                impact={"normal_pipeline": True},
            )
        )
    return candidates


def _conversational_act_candidate(
    conversation_state: ConversationState,
    message: Any,
    normalized: str,
    *,
    act: str,
    confidence: float,
    reason: str,
    signals: Sequence[str],
    target: Mapping[str, Any] | None = None,
    impact: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "contract": "conversational_act.v1",
        "act": act,
        "confidence": round(float(confidence), 4),
        "reason": reason,
        "evidence": {
            "raw_message": str(message),
            "normalized_message": normalized,
            "signals": list(signals),
            "pending_question_count": len(conversation_state.pending_questions),
            "active_mission_type": (conversation_state.active_mission or {}).get("type"),
        },
        "target": deepcopy(dict(target or {})),
        "impact": deepcopy(dict(impact or {})),
        "component": "conversation_state",
        "turn": int(conversation_state.turn_count),
    }


def _select_conversational_act(candidates: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    priority = {
        ConversationalActType.CORRECTION: 100,
        ConversationalActType.PENDING_ANSWER: 95,
        ConversationalActType.SIMPLIFICATION_REQUEST: 90,
        ConversationalActType.RECAP_REQUEST: 88,
        ConversationalActType.TOPIC_SHIFT: 86,
        ConversationalActType.CONTINUATION: 84,
        ConversationalActType.DEEPENING_REQUEST: 82,
        ConversationalActType.CLARIFICATION_REQUEST: 80,
        ConversationalActType.CLOSING: 70,
        ConversationalActType.CONFIRMATION: 60,
        ConversationalActType.NEGATION: 60,
        ConversationalActType.NEW_INFORMATION: 40,
        ConversationalActType.UNKNOWN: 0,
    }
    ordered = sorted(
        (dict(candidate) for candidate in candidates),
        key=lambda item: (float(item.get("confidence") or 0.0), priority.get(str(item.get("act")), 0)),
        reverse=True,
    )
    selected = dict(ordered[0])
    selected["alternatives"] = [
        {
            "act": item.get("act"),
            "confidence": item.get("confidence"),
            "reason": item.get("reason"),
        }
        for item in ordered[1:]
    ]
    return selected


def _act_suppresses_slot_resolution(conversational_act: Mapping[str, Any]) -> bool:
    act = str((conversational_act or {}).get("act") or "")
    return act in {
        ConversationalActType.CORRECTION,
        ConversationalActType.CLARIFICATION_REQUEST,
        ConversationalActType.TOPIC_SHIFT,
        ConversationalActType.RECAP_REQUEST,
        ConversationalActType.SIMPLIFICATION_REQUEST,
        ConversationalActType.DEEPENING_REQUEST,
        ConversationalActType.CLOSING,
    }


def _conversational_goal_for_act(
    conversation_state: ConversationState,
    act: Mapping[str, Any],
    *,
    source: str,
    goal_projection: Mapping[str, Any] | None = None,
    projection_metadata: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    act_name = str(act.get("act") or ConversationalActType.UNKNOWN)
    strategy_name = _strategy_for_act(conversation_state, act)
    projected_goal = deepcopy(dict((goal_projection or {}).get("primary_goal") or {}))
    metadata = deepcopy(dict(projection_metadata or {}))
    return {
        "contract": "conversational_goal.v1",
        "originating_act": deepcopy(dict(act)),
        "act": act_name,
        "intention": _goal_intention_for(act_name, strategy_name),
        "strategy": {
            "name": strategy_name,
            "response_plan": _response_plan_for_strategy(conversation_state, strategy_name),
            "owner": "conversation_state",
        },
        "success_criteria": _success_criteria_for(strategy_name),
        "abandonment_criteria": _abandonment_criteria_for(strategy_name),
        "priority": _goal_priority_for(strategy_name),
        "mission_impact": _mission_impact_for(conversation_state, strategy_name),
        "evidence": {
            "source": str(source),
            "semantic_goal": projected_goal,
            "semantic_projection_id": metadata.get("projection_id"),
            "semantic_representation_id": metadata.get("representation_id"),
            "act_confidence": act.get("confidence"),
            "active_mission": deepcopy(conversation_state.active_mission),
            "confirmed_facts": _active_fact_values(conversation_state.confirmed_facts),
            "pending_questions": [deepcopy(dict(item)) for item in conversation_state.pending_questions],
        },
        "fulfillment": {
            "status": "pending",
            "satisfied": False,
            "needs_second_attempt": False,
            "should_change_strategy": False,
            "evidence": {},
        },
        "component": "conversation_state",
        "turn": int(conversation_state.turn_count),
    }


def _strategy_for_act(conversation_state: ConversationState, act: Mapping[str, Any]) -> str:
    act_name = str(act.get("act") or "")
    if act_name == ConversationalActType.SIMPLIFICATION_REQUEST:
        return ConversationalStrategyType.SIMPLIFY
    if act_name == ConversationalActType.RECAP_REQUEST:
        return ConversationalStrategyType.SUMMARIZE
    if act_name == ConversationalActType.DEEPENING_REQUEST:
        return ConversationalStrategyType.DEEPEN
    if act_name == ConversationalActType.TOPIC_SHIFT:
        return ConversationalStrategyType.SWITCH_TOPIC
    if act_name == ConversationalActType.CONTINUATION:
        return ConversationalStrategyType.CONTINUE
    if act_name == ConversationalActType.CORRECTION:
        if (conversation_state.active_mission or {}).get("next_act") == "clarify_fact_revision" or (
            act.get("impact") or {}
        ).get("requires_clarification"):
            return ConversationalStrategyType.ASK_CLARIFICATION
        return ConversationalStrategyType.REPAIR
    if act_name == ConversationalActType.CLARIFICATION_REQUEST:
        return ConversationalStrategyType.ASK_CLARIFICATION
    if act_name == ConversationalActType.CLOSING:
        return ConversationalStrategyType.CLOSE
    return ConversationalStrategyType.RESPOND


def _goal_intention_for(act_name: str, strategy_name: str) -> str:
    return {
        ConversationalStrategyType.SIMPLIFY: "make_current_guidance_easier_to_understand",
        ConversationalStrategyType.SUMMARIZE: "summarize_confirmed_conversation_state",
        ConversationalStrategyType.DEEPEN: "provide_more_detail_about_current_focus",
        ConversationalStrategyType.CONTINUE: "continue_active_mission_from_current_next_act",
        ConversationalStrategyType.REPAIR: "repair_conversation_state_after_user_correction",
        ConversationalStrategyType.SWITCH_TOPIC: "recover_previous_available_focus_without_resetting_state",
        ConversationalStrategyType.CLOSE: "acknowledge_user_closure_and_pause",
        ConversationalStrategyType.ASK_CLARIFICATION: "ask_for_missing_conversational_target",
    }.get(strategy_name, f"respond_to_{act_name}")


def _success_criteria_for(strategy_name: str) -> list[str]:
    criteria = {
        ConversationalStrategyType.SIMPLIFY: [
            "response_uses_simple_wording",
            "response_preserves_active_mission",
            "response_mentions_next_action",
        ],
        ConversationalStrategyType.SUMMARIZE: [
            "response_contains_summary_marker",
            "response_uses_confirmed_facts_only",
        ],
        ConversationalStrategyType.DEEPEN: [
            "response_adds_detail",
            "response_preserves_current_topic",
        ],
        ConversationalStrategyType.CONTINUE: [
            "response_advances_current_next_act",
            "mission_not_restarted",
        ],
        ConversationalStrategyType.REPAIR: [
            "response_acknowledges_correction",
            "mission_uses_revised_fact",
        ],
        ConversationalStrategyType.SWITCH_TOPIC: [
            "response_acknowledges_topic_navigation",
            "response_recovers_available_focus",
        ],
        ConversationalStrategyType.ASK_CLARIFICATION: [
            "response_requests_specific_missing_target",
            "state_not_changed_by_guessing",
        ],
        ConversationalStrategyType.CLOSE: [
            "response_acknowledges_closure",
        ],
    }
    return criteria.get(strategy_name, ["response_generated"])


def _abandonment_criteria_for(strategy_name: str) -> list[str]:
    if strategy_name == ConversationalStrategyType.ASK_CLARIFICATION:
        return ["user_declines_to_clarify", "new_unrelated_topic_detected"]
    if strategy_name == ConversationalStrategyType.SWITCH_TOPIC:
        return ["no_previous_focus_available", "user_starts_new_topic"]
    return ["user_changes_act", "strategy_cannot_use_available_state"]


def _response_plan_for_strategy(conversation_state: ConversationState, strategy_name: str) -> Dict[str, Any]:
    mission = deepcopy(conversation_state.active_mission or {})
    direction = _topic_navigation_direction(
        normalize_text(
            ((conversation_state.last_conversational_act or {}).get("evidence") or {}).get("raw_message", "")
        ),
        conversation_state.last_conversational_act,
    )
    available_focus = _available_focus(conversation_state)
    if direction:
        available_focus["navigation_direction"] = direction
    return {
        "mode": strategy_name,
        "mission_type": mission.get("type"),
        "mission_next_act": mission.get("next_act"),
        "mission_status": mission.get("lifecycle_status"),
        "confirmed_facts": _active_fact_values(conversation_state.confirmed_facts),
        "pending_questions": [deepcopy(dict(item)) for item in conversation_state.pending_questions],
        "available_focus": available_focus,
        "topic_navigation_direction": direction,
    }


def _goal_priority_for(strategy_name: str) -> int:
    return {
        ConversationalStrategyType.ASK_CLARIFICATION: 95,
        ConversationalStrategyType.REPAIR: 92,
        ConversationalStrategyType.SIMPLIFY: 82,
        ConversationalStrategyType.SUMMARIZE: 80,
        ConversationalStrategyType.DEEPEN: 78,
        ConversationalStrategyType.SWITCH_TOPIC: 76,
        ConversationalStrategyType.CONTINUE: 70,
        ConversationalStrategyType.CLOSE: 50,
        ConversationalStrategyType.RESPOND: 40,
    }.get(strategy_name, 40)


def _mission_impact_for(conversation_state: ConversationState, strategy_name: str) -> Dict[str, Any]:
    mission = conversation_state.active_mission or {}
    return {
        "preserve_active_mission": strategy_name
        in {
            ConversationalStrategyType.SIMPLIFY,
            ConversationalStrategyType.SUMMARIZE,
            ConversationalStrategyType.DEEPEN,
            ConversationalStrategyType.CONTINUE,
            ConversationalStrategyType.ASK_CLARIFICATION,
            ConversationalStrategyType.REPAIR,
        },
        "active_mission_type": mission.get("type"),
        "next_act": mission.get("next_act"),
        # SWITCH_TOPIC is deliberately excluded from `preserve_active_mission`
        # and included here (ACA-305C section 1.4/5): a topic shift is exactly
        # the kind of evidence that may need to reevaluate the mission, not
        # preserve it untouched. This does not force a change -- it only makes
        # SWITCH_TOPIC-sourced evidence eligible for MissionManager's gate.
        "may_change_mission_state": strategy_name
        in {
            ConversationalStrategyType.REPAIR,
            ConversationalStrategyType.CONTINUE,
            ConversationalStrategyType.SWITCH_TOPIC,
        },
    }


def _active_fact_values(facts: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        str(key): _fact_value(value)
        for key, value in facts.items()
        if _is_active_fact_or_plain(value)
    }


def _available_focus(conversation_state: ConversationState) -> Dict[str, Any]:
    active_topic = _active_topic_from_stack(conversation_state.topic_stack)
    if active_topic:
        focus = deepcopy(dict(active_topic))
        if conversation_state.active_mission:
            focus.setdefault("active_mission_type", conversation_state.active_mission.get("type"))
            focus.setdefault("active_topic", conversation_state.active_mission.get("goal"))
        focus.setdefault("summary", active_topic.get("summary"))
        focus.setdefault("topic_id", active_topic.get("id"))
        focus.setdefault("topic_status", active_topic.get("status"))
        return focus
    if conversation_state.focus:
        focus = deepcopy(dict(conversation_state.focus))
        if conversation_state.active_mission:
            focus.setdefault("active_mission_type", conversation_state.active_mission.get("type"))
            focus.setdefault("active_topic", conversation_state.active_mission.get("goal"))
        return focus
    if conversation_state.active_mission:
        return {
            "active_mission_type": conversation_state.active_mission.get("type"),
            "active_topic": conversation_state.active_mission.get("goal"),
            "source": "active_mission",
        }
    return {}


def _evaluate_goal_fulfillment(goal: Mapping[str, Any], response: str) -> Dict[str, Any]:
    strategy_name = str(((goal.get("strategy") or {}).get("name")) or "")
    normalized_response = normalize_text(response)
    checks = _fulfillment_checks(strategy_name, normalized_response)
    satisfied = bool(response.strip()) and all(checks.values())
    return {
        "status": "satisfied" if satisfied else "needs_second_attempt",
        "satisfied": satisfied,
        "strategy": strategy_name,
        "checks": checks,
        "needs_second_attempt": not satisfied,
        "should_change_strategy": False,
        "evidence": {"response": response, "normalized_response": normalized_response},
        "component": "conversation_state",
    }


def _fulfillment_checks(strategy_name: str, normalized_response: str) -> Dict[str, bool]:
    if strategy_name == ConversationalStrategyType.SIMPLIFY:
        return {
            "simple_marker": "mas simple" in normalized_response,
            "not_empty": bool(normalized_response),
        }
    if strategy_name == ConversationalStrategyType.SUMMARIZE:
        return {
            "summary_marker": "resumen" in normalized_response,
            "uses_confirmed_facts": any(
                term in normalized_response
                for term in ("lesionados", "asegurado", "tercero", "denuncia", "documentacion")
            ),
        }
    if strategy_name == ConversationalStrategyType.DEEPEN:
        return {"detail_marker": "detalle" in normalized_response or "mas informacion" in normalized_response}
    if strategy_name == ConversationalStrategyType.CONTINUE:
        return {
            "continues_next_act": any(
                term in normalized_response
                for term in ("denuncia", "documentacion", "avanzar", "seguimiento")
            )
        }
    if strategy_name == ConversationalStrategyType.SWITCH_TOPIC:
        return {"topic_marker": any(term in normalized_response for term in ("volver", "foco", "tema", "retomo", "denuncia"))}
    if strategy_name == ConversationalStrategyType.ASK_CLARIFICATION:
        return {"asks_question": "?" in normalized_response or "necesito" in normalized_response or "que dato" in normalized_response}
    if strategy_name == ConversationalStrategyType.REPAIR:
        return {"repair_marker": "correccion" in normalized_response or "tomo" in normalized_response}
    if strategy_name == ConversationalStrategyType.CLOSE:
        return {"closure_marker": any(term in normalized_response for term in ("listo", "gracias", "cierro"))}
    return {"response_generated": bool(normalized_response)}


def _topic_navigation_direction(normalized: str, act: Mapping[str, Any] | None = None) -> str:
    if any(
        phrase in normalized
        for phrase in (
            "otra cosa",
            "cambiemos de tema",
            "hablemos de otra cosa",
            "cambiar de tema",
        )
    ):
        return "new_topic"
    if any(
        phrase in normalized
        for phrase in (
            "volvamos",
            "volver",
            "lo anterior",
            "tema anterior",
            "sobre lo anterior",
            "volvamos a eso",
            "volver a eso",
            "la denuncia",
            "denuncia",
        )
    ):
        if "sobre lo anterior" in normalized or "lo anterior" in normalized:
            return "indirect_previous"
        return "resume_previous"
    if _mentions_continuation(normalized):
        return "continue"
    target = dict((act or {}).get("target") or {})
    if target.get("direction"):
        return str(target["direction"])
    return "current"


def _topic_from_current_state(conversation_state: ConversationState, message: Any) -> Dict[str, Any] | None:
    mission = deepcopy(conversation_state.active_mission or {})
    if mission.get("type"):
        mission_type = str(mission["type"])
        topic_id = f"mission:{mission_type}"
        return {
            "contract": "conversation_topic.v1",
            "id": topic_id,
            "type": mission_type,
            "mission_type": mission_type,
            "mission_goal": mission.get("goal"),
            "conversational_goal": _topic_goal_snapshot(conversation_state.derived_state.get("conversation_goal")),
            "priority": 80,
            "status": TopicStatus.ACTIVE,
            "created_turn": _topic_created_turn(conversation_state.topic_stack, topic_id, conversation_state.turn_count),
            "last_active_turn": int(conversation_state.turn_count),
            "associated_facts": _topic_associated_facts(conversation_state, mission_type),
            "associated_slots": _topic_associated_slots(conversation_state, mission_type),
            "summary": _topic_summary(conversation_state, mission_type=mission_type, message=message),
        }
    focus_topic = conversation_state.focus.get("active_topic")
    if focus_topic:
        topic_id = f"focus:{normalize_text(focus_topic).replace(' ', '_')}"
        return {
            "contract": "conversation_topic.v1",
            "id": topic_id,
            "type": "focus",
            "mission_type": None,
            "mission_goal": conversation_state.focus.get("active_topic"),
            "conversational_goal": _topic_goal_snapshot(conversation_state.derived_state.get("conversation_goal")),
            "priority": 50,
            "status": TopicStatus.ACTIVE,
            "created_turn": _topic_created_turn(conversation_state.topic_stack, topic_id, conversation_state.turn_count),
            "last_active_turn": int(conversation_state.turn_count),
            "associated_facts": _topic_associated_facts(conversation_state, ""),
            "associated_slots": _topic_associated_slots(conversation_state, ""),
            "summary": str(focus_topic),
        }
    return None


def _new_unresolved_topic(conversation_state: ConversationState, message: Any) -> Dict[str, Any]:
    topic_id = f"topic:unresolved:{int(conversation_state.turn_count)}"
    summary = "Nuevo tema pendiente de definir"
    normalized = normalize_text(message)
    if normalized:
        summary = f"Nuevo tema pendiente de definir: {str(message).strip()}"
    return {
        "contract": "conversation_topic.v1",
        "id": topic_id,
        "type": "unresolved_topic",
        "mission_type": None,
        "mission_goal": None,
        "conversational_goal": _topic_goal_snapshot(conversation_state.derived_state.get("conversation_goal")),
        "priority": 30,
        "status": TopicStatus.ACTIVE,
        "created_turn": int(conversation_state.turn_count),
        "last_active_turn": int(conversation_state.turn_count),
        "associated_facts": {},
        "associated_slots": {},
        "summary": summary,
    }


def _topic_refreshed_from_state(topic: Mapping[str, Any], conversation_state: ConversationState) -> Dict[str, Any]:
    current = _topic_from_current_state(conversation_state, "")
    if current and topic.get("mission_type") and current.get("mission_type") == topic.get("mission_type"):
        refreshed = deepcopy(current)
        refreshed["id"] = topic.get("id") or refreshed["id"]
        refreshed["created_turn"] = topic.get("created_turn", refreshed["created_turn"])
        return refreshed
    refreshed = deepcopy(dict(topic))
    refreshed["last_active_turn"] = int(conversation_state.turn_count)
    if refreshed.get("mission_type"):
        refreshed["associated_facts"] = _topic_associated_facts(conversation_state, str(refreshed.get("mission_type")))
        refreshed["associated_slots"] = _topic_associated_slots(conversation_state, str(refreshed.get("mission_type")))
        refreshed["summary"] = _topic_summary(conversation_state, mission_type=str(refreshed.get("mission_type")), message="")
    return _normalize_topic(refreshed)


def _topic_with_status(topic: Mapping[str, Any], status: str, turn: int) -> Dict[str, Any]:
    updated = deepcopy(dict(topic))
    updated["status"] = status
    if status in TOPIC_ACTIVE_STATUSES:
        updated["last_active_turn"] = int(turn)
    return _normalize_topic(updated)


def _topic_is_unresolved_other(topic: Mapping[str, Any]) -> bool:
    return str(topic.get("type") or "") == "unresolved_topic"


def _resolve_topic_reference(
    stack: Sequence[Mapping[str, Any]],
    normalized: str,
    conversation_state: ConversationState,
) -> tuple[Dict[str, Any] | None, str, Dict[str, Any] | None]:
    candidates = [
        deepcopy(dict(topic))
        for topic in stack
        if str(topic.get("status") or "") in {TopicStatus.SUSPENDED, TopicStatus.ACTIVE, TopicStatus.RESUMED}
        and not _topic_is_unresolved_other(topic)
    ]
    if not candidates:
        return None, "no_topic_available", None

    scored: list[tuple[int, Dict[str, Any], list[str]]] = []
    for topic in candidates:
        score = int(topic.get("priority") or 0)
        evidence: list[str] = []
        text = " ".join(
            normalize_text(value)
            for value in (
                topic.get("type"),
                topic.get("mission_type"),
                topic.get("mission_goal"),
                topic.get("summary"),
            )
            if value
        )
        if str(topic.get("status")) == TopicStatus.SUSPENDED:
            score += 15
            evidence.append("suspended_topic")
        if "denuncia" in normalized and (
            "denuncia" in text or topic.get("mission_type") == "auto_claim_guidance"
        ):
            score += 45
            evidence.append("denuncia_reference")
        if any(term in normalized for term in ("lo anterior", "sobre lo anterior", "eso", "tema anterior")):
            score += int(topic.get("last_active_turn") or 0)
            evidence.append("previous_topic_reference")
        if _mentions_continuation(normalized):
            score += int(topic.get("last_active_turn") or 0)
            evidence.append("continuation_reference")
        if topic.get("mission_type") == (conversation_state.active_mission or {}).get("type"):
            score += 10
            evidence.append("active_mission_match")
        scored.append((score, topic, evidence))

    scored.sort(key=lambda item: (item[0], int(item[1].get("last_active_turn") or 0)), reverse=True)
    best_score, best_topic, best_evidence = scored[0]
    tied = [
        topic
        for score, topic, _ in scored
        if score == best_score and topic.get("id") != best_topic.get("id")
    ]
    if tied and not best_evidence:
        return None, "topic_reference_ambiguous", {
            "reason": "multiple_topics_with_same_score",
            "candidate_topic_ids": [best_topic.get("id")] + [topic.get("id") for topic in tied],
        }
    return best_topic, "+".join(best_evidence) or "most_recent_available_topic", None


def _topic_stack_with_conversational_goal(
    stack: Sequence[Mapping[str, Any]],
    *,
    goal: Mapping[str, Any],
    derived_state: Dict[str, Any],
    turn: int,
) -> list[Dict[str, Any]]:
    topics = [_normalize_topic(topic) for topic in stack if isinstance(topic, Mapping)]
    active = _active_topic_from_stack(topics)
    if not active:
        return topics
    updated_active = deepcopy(active)
    updated_active["conversational_goal"] = _topic_goal_snapshot({"goal": goal})
    updated_active["last_active_turn"] = int(turn)
    topics = _replace_topic(topics, updated_active)
    trace = derived_state.get("topic_stack")
    if isinstance(trace, dict):
        trace["active_topic"] = deepcopy(updated_active)
        trace["topics"] = deepcopy(topics)
        trace["summary_updated"] = updated_active.get("summary")
    return topics


def _topic_goal_snapshot(trace: Any) -> Dict[str, Any]:
    if not isinstance(trace, Mapping):
        return {}
    goal = dict(trace.get("goal") or trace)
    if not goal:
        return {}
    strategy = dict(goal.get("strategy") or {})
    return {
        "act": goal.get("act"),
        "intention": goal.get("intention"),
        "strategy": strategy.get("name"),
        "priority": goal.get("priority"),
        "turn": goal.get("turn"),
    }


def _topic_associated_facts(conversation_state: ConversationState, mission_type: str) -> Dict[str, Any]:
    associated: Dict[str, Any] = {}
    for fact_type, fact in conversation_state.confirmed_facts.items():
        if isinstance(fact, Mapping) and fact.get("contract") == "conversational_fact.v1":
            if mission_type and fact.get("mission_type") not in {mission_type, "", None}:
                continue
            if fact.get("status", FactStatus.ACTIVE) != FactStatus.ACTIVE:
                continue
            associated[str(fact_type)] = {
                "value": deepcopy(fact.get("value")),
                "confidence": fact.get("confidence"),
                "turn": fact.get("revised_turn") or fact.get("acquired_turn"),
            }
        elif fact_type in {"injuries", "user_role", "claim_report_loaded", "documentation_available"}:
            associated[str(fact_type)] = {"value": deepcopy(fact), "confidence": None, "turn": None}
    return associated


def _topic_associated_slots(conversation_state: ConversationState, mission_type: str) -> Dict[str, Any]:
    associated: Dict[str, Any] = {}
    for slot_name, slot in conversation_state.slots.items():
        if mission_type and slot.get("mission_type") not in {mission_type, "", None}:
            continue
        associated[str(slot_name)] = {
            "status": slot.get("status"),
            "value": deepcopy(slot.get("value")),
            "priority": slot.get("priority"),
        }
    return associated


def _topic_summary(conversation_state: ConversationState, *, mission_type: str, message: Any) -> str:
    if mission_type == "auto_claim_guidance":
        facts = _active_fact_values(conversation_state.confirmed_facts)
        pieces = ["Orientacion de denuncia de siniestro"]
        if facts.get("injuries") is False:
            pieces.append("no hubo lesionados")
        elif facts.get("injuries") is True:
            pieces.append("hubo lesionados")
        if facts.get("user_role") == "insured":
            pieces.append("sos asegurado")
        elif facts.get("user_role") == "third_party":
            pieces.append("sos tercero")
        if facts.get("claim_report_loaded") is True:
            pieces.append("la denuncia esta cargada")
        elif facts.get("claim_report_loaded") is False:
            pieces.append("la denuncia todavia no esta cargada")
        if facts.get("documentation_available") is True:
            pieces.append("tenes toda la documentacion")
        elif facts.get("documentation_available") is False:
            pieces.append("documentacion pendiente")
        next_act = (conversation_state.active_mission or {}).get("next_act")
        if next_act:
            pieces.append(f"proximo paso: {next_act}")
        return "; ".join(pieces)
    text = str(message or "").strip()
    return text or str((conversation_state.focus or {}).get("active_topic") or mission_type or "tema activo")


def _topic_created_turn(stack: Sequence[Mapping[str, Any]], topic_id: str, default_turn: int) -> int:
    existing = _find_topic_by_id(stack, topic_id)
    if existing and existing.get("created_turn") is not None:
        return int(existing.get("created_turn") or default_turn)
    return int(default_turn)


def _active_topic_from_stack(stack: Sequence[Mapping[str, Any]]) -> Dict[str, Any] | None:
    for topic in reversed(list(stack or [])):
        if str(topic.get("status") or "") in TOPIC_ACTIVE_STATUSES:
            return deepcopy(dict(topic))
    return None


def _find_topic_by_id(stack: Sequence[Mapping[str, Any]], topic_id: str) -> Dict[str, Any] | None:
    for topic in stack or ():
        if str(topic.get("id") or "") == topic_id:
            return deepcopy(dict(topic))
    return None


def _replace_topic(stack: Sequence[Mapping[str, Any]], replacement: Mapping[str, Any]) -> list[Dict[str, Any]]:
    replacement_id = str(replacement.get("id") or "")
    return [
        deepcopy(dict(replacement)) if str(topic.get("id") or "") == replacement_id else deepcopy(dict(topic))
        for topic in stack
    ]


def _remove_topic(stack: Sequence[Mapping[str, Any]], topic_id: str) -> list[Dict[str, Any]]:
    return [deepcopy(dict(topic)) for topic in stack if str(topic.get("id") or "") != topic_id]


def _normalize_topic(topic: Mapping[str, Any]) -> Dict[str, Any]:
    data = deepcopy(dict(topic))
    if not data:
        return {}
    if not data.get("id"):
        topic_type = str(data.get("type") or "topic")
        value = str(data.get("value") or data.get("mission_type") or data.get("mission_goal") or topic_type)
        data["id"] = f"{topic_type}:{normalize_text(value).replace(' ', '_')}"
    data.setdefault("contract", "conversation_topic.v1")
    data.setdefault("type", data.get("mission_type") or data.get("active_mission_type") or "topic")
    data.setdefault("mission_type", data.get("active_mission_type"))
    data.setdefault("mission_goal", data.get("active_topic") or data.get("value"))
    data.setdefault("conversational_goal", {})
    data.setdefault("priority", 50)
    if data.get("status") not in VALID_TOPIC_STATUSES:
        data["status"] = TopicStatus.ACTIVE
    data.setdefault("created_turn", 0)
    data.setdefault("last_active_turn", data.get("created_turn", 0))
    data.setdefault("associated_facts", {})
    data.setdefault("associated_slots", {})
    data.setdefault("summary", data.get("value") or data.get("mission_goal") or data.get("type") or "tema activo")
    return data


def _focus_from_active_topic(topic: Mapping[str, Any] | None, *, fallback: Mapping[str, Any]) -> Dict[str, Any]:
    if not topic:
        return deepcopy(dict(fallback or {}))
    focus = deepcopy(dict(fallback or {}))
    focus["active_topic_id"] = topic.get("id")
    focus["active_topic"] = topic.get("summary") or topic.get("mission_goal") or topic.get("type")
    focus["active_topic_type"] = topic.get("type")
    focus["topic_status"] = topic.get("status")
    if topic.get("mission_type"):
        focus["active_mission_type"] = topic.get("mission_type")
    focus["source"] = "topic_stack"
    return focus


def assimilate_user_facts(
    conversation_state: ConversationState,
    message: Any,
) -> tuple[ConversationState, list[Dict[str, Any]], Dict[str, Any] | None]:
    normalized = normalize_text(message)
    confirmed_facts = deepcopy(conversation_state.confirmed_facts)
    refuted_facts = deepcopy(conversation_state.refuted_facts)
    derived_state = deepcopy(conversation_state.derived_state)
    slots = deepcopy(conversation_state.slots)
    active_mission = deepcopy(conversation_state.active_mission) if conversation_state.active_mission else None
    acquired_facts = _candidate_facts_from_slot_resolution(conversation_state, message, normalized)
    acquired_facts.extend(_candidate_facts_from_message(conversation_state, message, normalized))
    withdrawal_requests, ambiguous_revisions = _candidate_fact_withdrawals(conversation_state, message, normalized)

    assimilated: list[Dict[str, Any]] = []
    confirmations: list[Dict[str, Any]] = []
    revisions: list[Dict[str, Any]] = []
    withdrawals: list[Dict[str, Any]] = []
    affected_fact_types: set[str] = set()
    withdrawn_fact_types: set[str] = set()

    for request in withdrawal_requests:
        fact_type = str(request["fact_type"])
        existing = confirmed_facts.get(fact_type)
        if existing is None:
            continue
        archived = _archived_fact(
            fact_type=fact_type,
            fact=existing,
            status=FactStatus.WITHDRAWN,
            reason=str(request.get("reason") or "user_withdrew_fact"),
            revised_turn=conversation_state.turn_count,
            evidence=dict(request.get("evidence") or {}),
            mission_type=_mission_type(conversation_state),
        )
        confirmed_facts.pop(fact_type, None)
        refuted_facts = _append_inactive_fact(refuted_facts, fact_type, archived)
        withdrawals.append(
            {
                "status": "withdrawn",
                "fact_type": fact_type,
                "original_fact": archived,
                "reason": archived.get("revision_reason"),
                "confidence": float(request.get("confidence") or 0.0),
                "evidence": deepcopy(dict(request.get("evidence") or {})),
                "component": "conversation_state",
            }
        )
        withdrawn_fact_types.add(fact_type)
        affected_fact_types.add(fact_type)

    for fact in acquired_facts:
        fact_type = str(fact["type"])
        existing = confirmed_facts.get(fact_type)
        existing_value = _fact_value(existing)
        existing_is_conversational_fact = (
            isinstance(existing, Mapping) and existing.get("contract") == "conversational_fact.v1"
        )
        if existing_is_conversational_fact and existing_value == fact["value"]:
            confirmed = _confirmed_fact(
                existing,
                fact,
                turn=conversation_state.turn_count,
            )
            confirmed_facts[fact_type] = confirmed
            confirmations.append(_fact_trace(fact, status="confirmed", previous=existing, current=confirmed))
            continue
        if existing is not None and existing_value != fact["value"]:
            revised, archived = _revised_fact(
                fact=fact,
                previous=existing,
                turn=conversation_state.turn_count,
                mission_type=_mission_type(conversation_state),
            )
            confirmed_facts[fact_type] = revised
            refuted_facts = _append_inactive_fact(refuted_facts, fact_type, archived)
            revisions.append(
                _fact_trace(
                    revised,
                    status="revised",
                    previous=archived,
                    current=revised,
                    revision={
                        "transition": f"{archived.get('status')}->{FactStatus.ACTIVE}",
                        "reason": revised.get("revision_reason"),
                        "confidence": revised.get("confidence"),
                    },
                )
            )
            affected_fact_types.add(fact_type)
            continue
        active_fact = _ensure_active_fact(fact)
        confirmed_facts[fact_type] = active_fact
        assimilated.append(_fact_trace(active_fact, status="assimilated", previous=existing))
        affected_fact_types.add(fact_type)

    slots = _slots_after_fact_changes(
        slots,
        confirmed_facts=confirmed_facts,
        affected_fact_types=affected_fact_types,
        withdrawn_fact_types=withdrawn_fact_types,
    )
    mission_advancement = _advance_mission(
        active_mission=active_mission,
        facts=confirmed_facts,
        slots=slots,
    )
    if mission_advancement:
        active_mission = mission_advancement["mission_after"]
    if ambiguous_revisions:
        clarification_advancement = _mission_with_revision_clarification(
            active_mission=active_mission,
            ambiguous_revisions=ambiguous_revisions,
        )
        if clarification_advancement:
            active_mission = clarification_advancement["mission_after"]
            mission_advancement = clarification_advancement

    if not assimilated and not confirmations and not revisions and not withdrawals and not ambiguous_revisions and not mission_advancement:
        return conversation_state, [], None

    trace = {
        "contract": "fact_assimilation_trace.v1",
        "component": "conversation_state",
        "message": str(message),
        "facts": [dict(item) for item in assimilated],
        "confirmations": [dict(item) for item in confirmations],
        "redundant_facts": [dict(item) for item in confirmations],
    }
    if assimilated or confirmations:
        derived_state["fact_assimilation"] = trace
    if revisions or withdrawals or ambiguous_revisions:
        derived_state["fact_revision"] = {
            "contract": "fact_revision_trace.v1",
            "component": "conversation_state",
            "message": str(message),
            "revisions": [dict(item) for item in revisions],
            "withdrawals": [dict(item) for item in withdrawals],
            "ambiguous_revisions": [dict(item) for item in ambiguous_revisions],
            "affected_slots": sorted(
                fact_type
                for fact_type in affected_fact_types | withdrawn_fact_types
                if fact_type in slots
            ),
            "mission_before": deepcopy(conversation_state.active_mission),
            "mission_after": deepcopy(active_mission),
        }
    if mission_advancement:
        derived_state["mission_advancement"] = {
            "contract": "mission_advancement_trace.v1",
            "component": "conversation_state",
            **{
                key: value
                for key, value in mission_advancement.items()
                if key != "mission_after"
            },
        }
        proposal = _mission_transition_proposal_from_advancement(
            mission_advancement,
            turn=conversation_state.turn_count,
        )
        if proposal:
            derived_state["mission_transition_proposals"] = [
                *(derived_state.get("mission_transition_proposals") or []),
                proposal,
            ]

    return (
        replace(
            conversation_state,
            slots=slots,
            confirmed_facts=confirmed_facts,
            refuted_facts=refuted_facts,
            active_mission=active_mission,
            pending_questions=_pending_questions_from_slots(
                _slots_from_mission(active_mission, source="mission_advancement") if active_mission else slots,
                source="mission_advancement",
            )
            if active_mission
            else conversation_state.pending_questions,
            derived_state=derived_state,
            projection_sources=_append_unique(
                conversation_state.projection_sources,
                "conversation_state.fact_assimilation",
                "conversation_state.fact_revision" if revisions or withdrawals or ambiguous_revisions else "",
                "conversation_state.mission_advancement" if mission_advancement else "",
            ),
        ),
        assimilated + confirmations + revisions + withdrawals + ambiguous_revisions,
        derived_state.get("mission_advancement"),
    )


def _candidate_facts_from_slot_resolution(
    conversation_state: ConversationState,
    message: Any,
    normalized: str,
) -> list[Dict[str, Any]]:
    trace = dict(conversation_state.derived_state.get("slot_resolution") or {})
    candidates: list[Dict[str, Any]] = []
    for resolution in trace.get("resolutions", []):
        if not isinstance(resolution, Mapping):
            continue
        if resolution.get("repeated") or not resolution.get("closed"):
            continue
        slot_name = str(resolution.get("slot") or "")
        if not slot_name:
            continue
        candidates.append(
            _conversational_fact(
                fact_type=slot_name,
                value=deepcopy(resolution.get("value")),
                origin="slot_resolution",
                confidence=float(resolution.get("confidence") or 0.0),
                mission_type=str(resolution.get("mission_type") or _mission_type(conversation_state)),
                acquired_turn=conversation_state.turn_count,
                evidence={
                    "raw_message": str(message),
                    "normalized_message": normalized,
                    "slot": slot_name,
                    "resolution_reason": resolution.get("reason"),
                    "question_resolved": dict(resolution.get("question_resolved") or {}),
                },
            )
        )
    return candidates


def _candidate_facts_from_message(
    conversation_state: ConversationState,
    message: Any,
    normalized: str,
) -> list[Dict[str, Any]]:
    candidates: list[Dict[str, Any]] = []
    mission_type = _mission_type(conversation_state)
    acquired_turn = conversation_state.turn_count
    all_required_loaded = _mentions_all_required_claim_information_loaded(normalized)
    if all_required_loaded:
        candidates.append(
            _conversational_fact(
                fact_type="claim_report_loaded",
                value=True,
                origin="user_message",
                confidence=0.84,
                mission_type=mission_type,
                acquired_turn=acquired_turn,
                evidence={"raw_message": str(message), "normalized_message": normalized, "reason": "all_required_claim_information_loaded"},
            )
        )
        candidates.append(
            _conversational_fact(
                fact_type="documentation_available",
                value=True,
                origin="user_message",
                confidence=0.82,
                mission_type=mission_type,
                acquired_turn=acquired_turn,
                evidence={"raw_message": str(message), "normalized_message": normalized, "reason": "all_required_claim_information_loaded"},
            )
        )
    if _mentions_claim_report_loaded(normalized):
        candidates.append(
            _conversational_fact(
                fact_type="claim_report_loaded",
                value=True,
                origin="user_message",
                confidence=0.88,
                mission_type=mission_type,
                acquired_turn=acquired_turn,
                evidence={"raw_message": str(message), "normalized_message": normalized},
            )
        )
    if not all_required_loaded and _mentions_documentation_available(normalized):
        candidates.append(
            _conversational_fact(
                fact_type="documentation_available",
                value=True,
                origin="user_message",
                confidence=0.86,
                mission_type=mission_type,
                acquired_turn=acquired_turn,
                evidence={"raw_message": str(message), "normalized_message": normalized},
            )
        )
    if _mentions_documentation_not_available(normalized, conversation_state):
        candidates.append(
            _conversational_fact(
                fact_type="documentation_available",
                value=False,
                origin="user_correction",
                confidence=0.78,
                mission_type=mission_type,
                acquired_turn=acquired_turn,
                evidence={"raw_message": str(message), "normalized_message": normalized},
            )
        )
    if _mentions_no_injuries(normalized):
        candidates.append(
            _conversational_fact(
                fact_type="injuries",
                value=False,
                origin="user_message",
                confidence=0.84,
                mission_type=mission_type,
                acquired_turn=acquired_turn,
                evidence={"raw_message": str(message), "normalized_message": normalized},
            )
        )
    if _mentions_injuries_present(normalized):
        candidates.append(
            _conversational_fact(
                fact_type="injuries",
                value=True,
                origin="user_message",
                confidence=0.86,
                mission_type=mission_type,
                acquired_turn=acquired_turn,
                evidence={"raw_message": str(message), "normalized_message": normalized},
            )
        )
    if _mentions_user_third_party(normalized):
        candidates.append(
            _conversational_fact(
                fact_type="user_role",
                value="third_party",
                origin="user_message",
                confidence=0.88,
                mission_type=mission_type,
                acquired_turn=acquired_turn,
                evidence={"raw_message": str(message), "normalized_message": normalized},
            )
        )
    elif _mentions_user_insured(normalized):
        candidates.append(
            _conversational_fact(
                fact_type="user_role",
                value="insured",
                origin="user_message",
                confidence=0.86,
                mission_type=mission_type,
                acquired_turn=acquired_turn,
                evidence={"raw_message": str(message), "normalized_message": normalized},
            )
        )
    if _mentions_claim_report_not_loaded(normalized, conversation_state):
        candidates.append(
            _conversational_fact(
                fact_type="claim_report_loaded",
                value=False,
                origin="user_correction",
                confidence=0.82,
                mission_type=mission_type,
                acquired_turn=acquired_turn,
                evidence={"raw_message": str(message), "normalized_message": normalized},
            )
        )
    return candidates


def _candidate_fact_withdrawals(
    conversation_state: ConversationState,
    message: Any,
    normalized: str,
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    if not _is_generic_withdrawal(normalized):
        return [], []
    latest = _latest_active_fact_types(conversation_state.confirmed_facts)
    evidence = {
        "raw_message": str(message),
        "normalized_message": normalized,
    }
    if len(latest) == 1:
        return (
            [
                {
                    "fact_type": latest[0],
                    "confidence": 0.68,
                    "reason": "user_withdrew_latest_fact",
                    "evidence": evidence,
                }
            ],
            [],
        )
    return (
        [],
        [
            {
                "status": "ambiguous",
                "reason": "withdrawal_target_not_clear",
                "candidate_facts": latest,
                "confidence": 0.36,
                "evidence": evidence,
                "component": "conversation_state",
            }
        ],
    )


def _conversational_fact(
    *,
    fact_type: str,
    value: Any,
    origin: str,
    confidence: float,
    mission_type: str,
    acquired_turn: int,
    evidence: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "contract": "conversational_fact.v1",
        "type": fact_type,
        "value": deepcopy(value),
        "origin": origin,
        "confidence": round(float(confidence), 4),
        "mission_type": mission_type,
        "acquired_turn": int(acquired_turn),
        "evidence": deepcopy(dict(evidence)),
        "status": FactStatus.ACTIVE,
        "history": [],
    }


def _fact_trace(
    fact: Mapping[str, Any],
    *,
    status: str,
    previous: Any,
    current: Any | None = None,
    revision: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    trace = {
        "status": status,
        "fact": deepcopy(dict(fact)),
        "previous": deepcopy(previous),
        "component": "conversation_state",
    }
    if current is not None:
        trace["current"] = deepcopy(current)
    if revision is not None:
        trace["revision"] = deepcopy(dict(revision))
    return trace


def _ensure_active_fact(fact: Mapping[str, Any]) -> Dict[str, Any]:
    active = deepcopy(dict(fact))
    active.setdefault("status", FactStatus.ACTIVE)
    active.setdefault("history", [])
    return active


def _confirmed_fact(existing: Mapping[str, Any], observed: Mapping[str, Any], *, turn: int) -> Dict[str, Any]:
    confirmed = _ensure_active_fact(existing)
    confirmed["confidence"] = max(
        float(confirmed.get("confidence") or 0.0),
        float(observed.get("confidence") or 0.0),
    )
    confirmations = list(confirmed.get("confirmations") or [])
    confirmations.append(
        {
            "turn": int(turn),
            "confidence": float(observed.get("confidence") or 0.0),
            "evidence": deepcopy(dict(observed.get("evidence") or {})),
            "origin": observed.get("origin"),
        }
    )
    confirmed["confirmations"] = confirmations
    confirmed["last_confirmed_turn"] = int(turn)
    return confirmed


def _revised_fact(
    *,
    fact: Mapping[str, Any],
    previous: Any,
    turn: int,
    mission_type: str,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    fact_type = str(fact.get("type") or "")
    previous_value = _fact_value(previous)
    new_value = deepcopy(fact.get("value"))
    previous_status = _inactive_status_for_revision(previous_value, new_value)
    reason = _revision_reason(previous_value, new_value)
    archived = _archived_fact(
        fact_type=fact_type,
        fact=previous,
        status=previous_status,
        reason=reason,
        revised_turn=turn,
        evidence=dict(fact.get("evidence") or {}),
        mission_type=mission_type,
    )
    revised = _ensure_active_fact(fact)
    previous_history = _fact_history(previous)
    revised["history"] = previous_history + [archived]
    revised["replaced_fact"] = archived
    revised["revision_reason"] = reason
    revised["revised_turn"] = int(turn)
    revised["revision_evidence"] = deepcopy(dict(fact.get("evidence") or {}))
    revised["confidence"] = max(0.5, round(float(fact.get("confidence") or 0.0) * 0.96, 4))
    return revised, archived


def _archived_fact(
    *,
    fact_type: str,
    fact: Any,
    status: str,
    reason: str,
    revised_turn: int,
    evidence: Mapping[str, Any],
    mission_type: str,
) -> Dict[str, Any]:
    if isinstance(fact, Mapping) and fact.get("contract") == "conversational_fact.v1":
        archived = deepcopy(dict(fact))
        archived.pop("history", None)
    else:
        archived = _conversational_fact(
            fact_type=fact_type,
            value=deepcopy(fact),
            origin="legacy_fact",
            confidence=0.5,
            mission_type=mission_type,
            acquired_turn=0,
            evidence={},
        )
        archived.pop("history", None)
    archived["status"] = status
    archived["revision_reason"] = reason
    archived["revised_turn"] = int(revised_turn)
    archived["revision_evidence"] = deepcopy(dict(evidence))
    return archived


def _fact_history(fact: Any) -> list[Dict[str, Any]]:
    if not isinstance(fact, Mapping):
        return []
    history = fact.get("history")
    if not isinstance(history, list):
        return []
    return [deepcopy(dict(item)) for item in history if isinstance(item, Mapping)]


def _inactive_status_for_revision(previous_value: Any, new_value: Any) -> str:
    if isinstance(previous_value, bool) and isinstance(new_value, bool):
        return FactStatus.REFUTED
    return FactStatus.SUPERSEDED


def _revision_reason(previous_value: Any, new_value: Any) -> str:
    if isinstance(previous_value, bool) and isinstance(new_value, bool):
        if previous_value is True and new_value is False:
            return "user_negated_previous_fact"
        if previous_value is False and new_value is True:
            return "user_corrected_previous_negation"
    return "user_replaced_previous_fact"


def _append_inactive_fact(refuted_facts: Mapping[str, Any], fact_type: str, archived: Mapping[str, Any]) -> Dict[str, Any]:
    updated = deepcopy(dict(refuted_facts or {}))
    values = list(updated.get(fact_type) or [])
    values.append(deepcopy(dict(archived)))
    updated[fact_type] = values
    return updated


def _slots_after_fact_changes(
    slots: Mapping[str, Mapping[str, Any]],
    *,
    confirmed_facts: Mapping[str, Any],
    affected_fact_types: set[str],
    withdrawn_fact_types: set[str],
) -> Dict[str, Dict[str, Any]]:
    updated = {name: dict(slot) for name, slot in (slots or {}).items()}
    for fact_type in sorted(affected_fact_types | withdrawn_fact_types):
        if fact_type not in {"injuries", "user_role"}:
            continue
        if fact_type in withdrawn_fact_types or fact_type not in confirmed_facts:
            slot = dict(updated.get(fact_type) or {})
            slot.update(
                {
                    "name": fact_type,
                    "status": SlotStatus.PENDING,
                    "value": None,
                    "confidence": 0.0,
                    "evidence": {"source": "fact_revision", "reason": "fact_withdrawn"},
                    "updated_by": "conversation_state.fact_revision",
                }
            )
            slot.pop("closed_by", None)
            updated[fact_type] = slot
            continue
        fact = confirmed_facts[fact_type]
        if not _is_active_conversational_fact(fact):
            continue
        slot = dict(updated.get(fact_type) or {})
        slot.update(
            {
                "name": fact_type,
                "status": SlotStatus.ANSWERED,
                "value": deepcopy(fact.get("value")),
                "confidence": float(fact.get("confidence") or 0.0),
                "evidence": deepcopy(dict(fact.get("evidence") or {})),
                "updated_by": "conversation_state.fact_revision",
                "closed_by": "fact_revision" if fact.get("replaced_fact") else "fact_assimilation",
            }
        )
        updated[fact_type] = slot
    return updated


def _mission_with_revision_clarification(
    *,
    active_mission: Dict[str, Any] | None,
    ambiguous_revisions: Sequence[Mapping[str, Any]],
) -> Dict[str, Any] | None:
    if not active_mission or not ambiguous_revisions:
        return None
    before = deepcopy(active_mission)
    mission = deepcopy(active_mission)
    mission["next_act"] = "clarify_fact_revision"
    blockers = list(mission.get("blockers") or [])
    if "fact_revision_target_unknown" not in blockers:
        blockers.append("fact_revision_target_unknown")
    mission["blockers"] = blockers
    mission["status"] = "in_progress"
    mission["lifecycle_status"] = MissionLifecycleStatus.WAITING_USER
    if mission == before:
        return None
    return {
        "mission_before": before,
        "mission_after": mission,
        "from_status": str(before.get("lifecycle_status") or MissionLifecycleStatus.INITIALIZED),
        "to_status": MissionLifecycleStatus.WAITING_USER,
        "reason": "ambiguous_fact_revision_requires_clarification",
        "next_act": "clarify_fact_revision",
        "facts_considered": {},
        "component": "conversation_state",
    }


def _latest_active_fact_types(facts: Mapping[str, Any]) -> list[str]:
    latest_turn = None
    candidates: list[str] = []
    for fact_type, fact in facts.items():
        if not _is_active_conversational_fact(fact):
            continue
        turn = int(fact.get("revised_turn") or fact.get("acquired_turn") or 0)
        if latest_turn is None or turn > latest_turn:
            latest_turn = turn
            candidates = [str(fact_type)]
        elif turn == latest_turn:
            candidates.append(str(fact_type))
    return sorted(candidates)


def _is_active_conversational_fact(fact: Any) -> bool:
    return (
        isinstance(fact, Mapping)
        and fact.get("contract") == "conversational_fact.v1"
        and fact.get("status", FactStatus.ACTIVE) == FactStatus.ACTIVE
    )


def _advance_mission(
    *,
    active_mission: Dict[str, Any] | None,
    facts: Mapping[str, Any],
    slots: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any] | None:
    if not active_mission or active_mission.get("type") != "auto_claim_guidance":
        return None

    before = deepcopy(active_mission)
    mission = deepcopy(active_mission)
    fact_values = {
        key: _fact_value(value)
        for key, value in facts.items()
        if _is_active_fact_or_plain(value)
    }
    missing_slots = [
        name
        for name, slot in slots.items()
        if slot.get("status") in {SlotStatus.PENDING, SlotStatus.PARTIALLY_FILLED}
    ]
    mission["slots"] = {name: dict(slot) for name, slot in slots.items()}
    mission["facts"] = _mission_fact_snapshot(facts)
    mission["missing"] = missing_slots
    mission["blockers"] = _blockers_for_missing(missing_slots)

    previous_status = str(mission.get("lifecycle_status") or MissionLifecycleStatus.INITIALIZED)
    new_status = _mission_status_for(fact_values=fact_values, missing_slots=missing_slots)
    if new_status not in MISSION_LIFECYCLE.get(previous_status, ()) and previous_status != new_status:
        new_status = _safe_mission_transition(previous_status, new_status)
    next_act = _next_act_for_mission(fact_values=fact_values, missing_slots=missing_slots, status=new_status)
    mission["lifecycle_status"] = new_status
    mission["next_act"] = next_act
    mission["progress"] = _mission_progress_for(fact_values=fact_values, missing_slots=missing_slots, status=new_status)
    mission["status"] = _legacy_mission_status(new_status)

    if mission == before:
        return None
    return {
        "mission_before": before,
        "mission_after": mission,
        "from_status": previous_status,
        "to_status": new_status,
        "reason": _mission_advancement_reason(fact_values=fact_values, missing_slots=missing_slots, next_act=next_act),
        "next_act": next_act,
        "facts_considered": {key: deepcopy(value) for key, value in fact_values.items()},
        "component": "conversation_state",
    }


def _mission_status_for(*, fact_values: Mapping[str, Any], missing_slots: Sequence[str]) -> str:
    if missing_slots:
        return MissionLifecycleStatus.WAITING_USER
    if fact_values.get("claim_report_loaded") is True and fact_values.get("documentation_available") is True:
        return MissionLifecycleStatus.PROGRESSING
    if fact_values.get("injuries") is not None and fact_values.get("user_role") is not None:
        return MissionLifecycleStatus.READY_TO_PROGRESS
    if fact_values:
        return MissionLifecycleStatus.GATHERING_INFORMATION
    return MissionLifecycleStatus.INITIALIZED


def _next_act_for_mission(*, fact_values: Mapping[str, Any], missing_slots: Sequence[str], status: str) -> str:
    if missing_slots:
        if "injuries" in missing_slots:
            return "ask_injuries"
        if "user_role" in missing_slots:
            return "ask_user_role"
        return "ask_missing_information"
    if fact_values.get("injuries") is True:
        return "prioritize_injury_assistance"
    if fact_values.get("claim_report_loaded") is not True:
        return "check_claim_report_loaded"
    if fact_values.get("documentation_available") is not True:
        return "check_documentation_available"
    if status == MissionLifecycleStatus.PROGRESSING:
        return "provide_next_step_guidance"
    return "continue_guidance"


def _mission_progress_for(*, fact_values: Mapping[str, Any], missing_slots: Sequence[str], status: str) -> float:
    if status == MissionLifecycleStatus.PROGRESSING:
        return 0.9
    if status == MissionLifecycleStatus.READY_TO_PROGRESS:
        return 0.72
    if missing_slots:
        return 0.35 if len(missing_slots) == 1 else 0.2
    if fact_values:
        return 0.5
    return 0.1


def _legacy_mission_status(lifecycle_status: str) -> str:
    if lifecycle_status == MissionLifecycleStatus.COMPLETED:
        return "completed"
    if lifecycle_status == MissionLifecycleStatus.SUSPENDED:
        return "suspended"
    return "in_progress"


def _safe_mission_transition(previous_status: str, target_status: str) -> str:
    if previous_status == MissionLifecycleStatus.INITIALIZED:
        return MissionLifecycleStatus.GATHERING_INFORMATION
    if target_status in MISSION_LIFECYCLE.get(previous_status, ()):
        return target_status
    return previous_status


def _mission_advancement_reason(*, fact_values: Mapping[str, Any], missing_slots: Sequence[str], next_act: str) -> str:
    if missing_slots:
        return f"mission_waiting_for_{missing_slots[0]}"
    if next_act == "check_claim_report_loaded":
        return "core_slots_answered_check_claim_report"
    if next_act == "check_documentation_available":
        return "claim_report_loaded_check_documentation"
    if next_act == "provide_next_step_guidance":
        return "claim_report_and_documentation_ready"
    if next_act == "prioritize_injury_assistance":
        return "injuries_confirmed_prioritize_assistance"
    if fact_values:
        return "facts_assimilated"
    return "mission_initialized"


def _mission_fact_snapshot(facts: Mapping[str, Any]) -> Dict[str, Any]:
    snapshot = {}
    for key, fact in facts.items():
        if _is_active_conversational_fact(fact):
            snapshot[key] = {
                "value": deepcopy(fact.get("value")),
                "confidence": fact.get("confidence"),
                "origin": fact.get("origin"),
                "acquired_turn": fact.get("acquired_turn"),
                "status": fact.get("status"),
            }
    return snapshot


def _blockers_for_missing(missing_slots: Sequence[str]) -> list[str]:
    return [f"{slot}_unknown" for slot in missing_slots]


def _fact_value(value: Any) -> Any:
    if isinstance(value, Mapping) and value.get("contract") == "conversational_fact.v1":
        return deepcopy(value.get("value"))
    return deepcopy(value)


MISSION_TRANSITION_PROPOSAL_CONTRACT = "mission_transition_proposal.v1"


def _mission_transition_proposal_from_advancement(
    advancement: Mapping[str, Any] | None,
    *,
    turn: int,
    transition_type: str = "maintain",
    evidence_kind: str = "fact_slot_delta",
    confidence: float = 1.0,
) -> Dict[str, Any] | None:
    """Reshape an internal advancement trace (`_advance_mission` /
    `_mission_with_revision_clarification`) into an inert
    MissionTransitionProposal (ACA-305B section 3, section 8).

    The proposal never carries a final `mission_after` -- only the
    `mission_before` snapshot the advancement was computed against and the
    `mission_delta` fields it changed. Only `MissionManager` may merge them
    into a result; this function performs no write and makes no decision.
    """

    if not advancement:
        return None
    mission_before = deepcopy(advancement.get("mission_before") or {})
    mission_after = advancement.get("mission_after") or {}
    mission_delta = {
        key: deepcopy(value)
        for key, value in mission_after.items()
        if mission_before.get(key) != value or key not in mission_before
    }
    if not mission_delta:
        return None
    proposal_id = "|".join(
        [
            "conversation_state",
            str(turn),
            transition_type,
            str(advancement.get("reason") or ""),
            str(advancement.get("to_status") or ""),
        ]
    )
    return {
        "contract": MISSION_TRANSITION_PROPOSAL_CONTRACT,
        "proposal_id": proposal_id,
        "component": "conversation_state",
        "turn": int(turn),
        "transition_type": transition_type,
        "target_mission_type": None,
        "mission_before": mission_before,
        "mission_delta": mission_delta,
        "evidence": {
            "evidence_kind": evidence_kind,
            "facts_considered": deepcopy(advancement.get("facts_considered") or {}),
            "from_status": advancement.get("from_status"),
            "to_status": advancement.get("to_status"),
        },
        "confidence": float(confidence),
        "reason": str(advancement.get("reason") or ""),
    }


def _is_active_fact_or_plain(value: Any) -> bool:
    if isinstance(value, Mapping) and value.get("contract") == "conversational_fact.v1":
        return value.get("status", FactStatus.ACTIVE) == FactStatus.ACTIVE
    return True


def _mission_type(conversation_state: ConversationState) -> str:
    return str((conversation_state.active_mission or {}).get("type") or "")


def _mentions_claim_report_loaded(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "denuncia ya esta cargada",
            "denuncia ya esta hecha",
            "ya cargue la denuncia",
            "ya hice la denuncia",
            "denuncia cargada",
            "la denuncia esta cargada",
        )
    )


def _mentions_all_required_claim_information_loaded(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "ya cargue todo",
            "ya esta todo cargado",
            "ya subi todo",
            "ya mande todo",
            "ya complete todo",
            "tengo todo cargado",
            "cargue todo",
        )
    )


def _mentions_claim_report_not_loaded(normalized: str, conversation_state: ConversationState) -> bool:
    explicit = any(
        phrase in normalized
        for phrase in (
            "denuncia no esta cargada",
            "la denuncia no esta cargada",
            "no esta cargada la denuncia",
            "no cargue la denuncia",
            "todavia no cargue la denuncia",
            "aun no cargue la denuncia",
        )
    )
    if explicit:
        return True
    previous = conversation_state.confirmed_facts.get("claim_report_loaded")
    previous_loaded = _fact_value(previous) is True
    return previous_loaded and _has_correction_cue(normalized) and normalized.strip(" .!?") in {
        "perdon, todavia no",
        "perdon todavia no",
        "perdon, aun no",
        "perdon aun no",
        "todavia no",
        "aun no",
        "no",
    }


def _mentions_documentation_available(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "tengo toda la documentacion",
            "tengo todos los documentos",
            "tengo la documentacion",
            "documentacion completa",
            "ya tengo todo",
        )
    )


def _mentions_documentation_not_available(normalized: str, conversation_state: ConversationState) -> bool:
    explicit = any(
        phrase in normalized
        for phrase in (
            "no tengo toda la documentacion",
            "no tengo la documentacion",
            "todavia no tengo la documentacion",
            "aun no tengo la documentacion",
            "me falta documentacion",
            "me faltan documentos",
        )
    )
    if explicit:
        return True
    previous = conversation_state.confirmed_facts.get("documentation_available")
    previous_available = _fact_value(previous) is True
    next_act = str((conversation_state.active_mission or {}).get("next_act") or "")
    return (
        previous_available
        and next_act == "provide_next_step_guidance"
        and _has_correction_cue(normalized)
        and normalized.strip(" .!?") in {"perdon, todavia no", "perdon todavia no", "todavia no", "aun no", "no"}
    )


def _mentions_no_injuries(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "no hubo lesionados",
            "no hay lesionados",
            "sin lesionados",
            "nadie lesionado",
        )
    )


def _mentions_injuries_present(normalized: str) -> bool:
    if _mentions_no_injuries(normalized):
        return False
    return any(
        phrase in normalized
        for phrase in (
            "si hubo lesionados",
            "hubo lesionados",
            "hay lesionados",
            "hubo heridos",
            "hay heridos",
            "alguien lesionado",
            "alguien lastimado",
            "vino la ambulancia",
        )
    )


def _mentions_user_third_party(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "soy tercero",
            "soy tercera",
            "tercero damnificado",
            "tercera damnificada",
            "soy damnificado",
            "soy damnificada",
            "no soy asegurado",
            "no soy asegurada",
        )
    )


def _mentions_user_insured(normalized: str) -> bool:
    if _mentions_user_third_party(normalized):
        return False
    return any(
        phrase in normalized
        for phrase in (
            "soy asegurado",
            "soy asegurada",
            "soy cliente",
            "mi poliza",
            "mi seguro",
        )
    )


def _has_correction_cue(normalized: str) -> bool:
    return any(
        cue in normalized
        for cue in (
            "perdon",
            "corrijo",
            "en realidad",
            "me equivoque",
            "me confundi",
            "quise decir",
            "no,",
            "no ",
        )
    )


def _looks_like_correction(normalized: str, revisable_targets: Sequence[str]) -> bool:
    if _is_generic_withdrawal(normalized):
        return True
    if revisable_targets and _has_correction_cue(normalized):
        return True
    if revisable_targets and any(
        phrase in normalized
        for phrase in (
            "si hubo lesionados",
            "no hubo lesionados",
            "soy tercero",
            "soy tercera",
            "soy asegurado",
            "soy asegurada",
            "todavia no",
            "aun no",
        )
    ):
        return True
    return False


def _active_fact_targets_for_message(conversation_state: ConversationState, normalized: str) -> list[str]:
    targets: list[str] = []
    facts = conversation_state.confirmed_facts
    if "injuries" in facts and (_mentions_no_injuries(normalized) or _mentions_injuries_present(normalized)):
        targets.append("injuries")
    if "user_role" in facts and (_mentions_user_insured(normalized) or _mentions_user_third_party(normalized)):
        targets.append("user_role")
    if "claim_report_loaded" in facts and (
        _mentions_claim_report_loaded(normalized)
        or _mentions_claim_report_not_loaded(normalized, conversation_state)
    ):
        targets.append("claim_report_loaded")
    if "documentation_available" in facts and (
        _mentions_documentation_available(normalized)
        or _mentions_documentation_not_available(normalized, conversation_state)
    ):
        targets.append("documentation_available")
    if _is_generic_withdrawal(normalized):
        targets.extend(_latest_active_fact_types(facts))
    return sorted(set(targets))


def _looks_like_pending_answer(
    normalized: str,
    pending_slots: Sequence[str],
    pending_questions: Sequence[Mapping[str, Any]],
) -> bool:
    if not pending_slots:
        return False
    explicit = _explicit_slot_matches(normalized, pending_slots)
    if explicit:
        return True
    contextual = _contextual_slot_match(normalized, pending_slots, pending_questions)
    return contextual is not None and _clears_generic_slot_confidence_floor(contextual)


def _is_minimal_affirmation_or_negation(normalized: str) -> bool:
    return _is_affirmation(normalized) or _is_negation(normalized)


def _is_affirmation(normalized: str) -> bool:
    return normalized.strip(" .!?") in {
        "si",
        "sí",
        "sip",
        "claro",
        "correcto",
        "exacto",
        "asi es",
        "dale",
    }


def _is_negation(normalized: str) -> bool:
    stripped = normalized.strip(" .!?")
    return stripped in {
        "no",
        "nop",
        "para nada",
        "negativo",
    } or stripped.startswith("no,") or stripped.startswith("no ")


def _mentions_simplification_request(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "explicamelo mas simple",
            "explicalo mas simple",
            "mas simple",
            "en simple",
            "no entendi",
            "no lo entendi",
            "decimelo facil",
        )
    )


def _mentions_recap_request(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "resumime",
            "resumen",
            "recapitulame",
            "que dijimos",
            "haceme un resumen",
        )
    )


def _mentions_topic_shift(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "volvamos a lo anterior",
            "volver a lo anterior",
            "volvamos al tema anterior",
            "volvamos a la denuncia",
            "volver a la denuncia",
            "sobre lo anterior",
            "y sobre lo anterior",
            "volvamos a eso",
            "volver a eso",
            "cambiemos de tema",
            "cambiar de tema",
            "otra cosa",
            "hablemos de otra cosa",
        )
    )


def _mentions_continuation(normalized: str) -> bool:
    return normalized.strip(" .!?") in {
        "seguimos",
        "sigamos",
        "continuemos",
        "avancemos",
        "seguí",
        "segui",
        "dale seguimos",
        "dale sigamos",
    }


def _mentions_deepening_request(normalized: str) -> bool:
    return any(
        phrase in normalized
        for phrase in (
            "mas detalle",
            "dame mas detalle",
            "profundiza",
            "explicamelo mejor",
            "contame mas",
            "mas informacion",
        )
    )


def _mentions_clarification_request(normalized: str) -> bool:
    if _mentions_simplification_request(normalized) or _mentions_deepening_request(normalized):
        return False
    return any(
        phrase in normalized
        for phrase in (
            "que queres decir",
            "a que te referis",
            "me aclaras",
            "aclarame",
            "no entiendo",
            "no me queda claro",
        )
    )


def _mentions_closing(normalized: str) -> bool:
    return normalized.strip(" .!?") in {
        "gracias",
        "listo",
        "eso es todo",
        "chau",
        "adios",
        "hasta luego",
    }


def _is_generic_withdrawal(normalized: str) -> bool:
    stripped = normalized.strip(" .!?")
    return stripped in {
        "me confundi",
        "me equivoque",
        "perdon me confundi",
        "perdon, me confundi",
        "perdon me equivoque",
        "perdon, me equivoque",
        "no, me equivoque",
        "no me equivoque",
        "retiro lo dicho",
    }


def _ordered_pending_slot_names(
    slots: Mapping[str, Mapping[str, Any]],
    pending_questions: Sequence[Mapping[str, Any]],
) -> list[str]:
    priority_by_slot = {
        str(question.get("slot")): int(question.get("priority", 100) or 100)
        for question in pending_questions
        if question.get("slot")
    }
    ordered = sorted(
        (
            str(name)
            for name, slot in slots.items()
            if slot.get("status") in {SlotStatus.PENDING, SlotStatus.PARTIALLY_FILLED}
        ),
        key=lambda slot_name: (priority_by_slot.get(slot_name, _slot_priority(slot_name)), slot_name),
    )
    return ordered


def _explicit_slot_matches(normalized: str, pending_slots: Sequence[str]) -> list[Dict[str, Any]]:
    matches: list[Dict[str, Any]] = []
    for slot_name in pending_slots:
        match = _match_slot_answer(slot_name, normalized, contextual=False)
        if match is not None:
            matches.append(match)
    return matches


def _contextual_slot_match(
    normalized: str,
    pending_slots: Sequence[str],
    pending_questions: Sequence[Mapping[str, Any]],
) -> Dict[str, Any] | None:
    if not pending_slots:
        return None
    primary_slot = pending_slots[0]
    return _match_slot_answer(
        primary_slot,
        normalized,
        contextual=True,
        pending_question=_question_for_slot(primary_slot, pending_questions),
    )


def _match_slot_answer(
    slot_name: str,
    normalized: str,
    *,
    contextual: bool,
    pending_question: Mapping[str, Any] | None = None,
) -> Dict[str, Any] | None:
    if slot_name == "injuries":
        return _match_injuries(normalized, contextual=contextual)
    if slot_name == "user_role":
        return _match_user_role(normalized, contextual=contextual, pending_question=pending_question)
    return _match_generic_slot(slot_name, normalized, contextual=contextual)


def _match_injuries(normalized: str, *, contextual: bool) -> Dict[str, Any] | None:
    if _is_uncertain(normalized):
        return _slot_match(
            slot="injuries",
            value="unknown",
            confidence=0.45,
            status=SlotStatus.PARTIALLY_FILLED,
            evidence=normalized,
            reason="user_uncertain_about_injuries",
            close=False,
        )
    negative = (
        "no",
        "no hubo",
        "sin lesionados",
        "nadie lesionado",
        "ningun lesionado",
        "ninguno lesionado",
        "no hay lesionados",
        "no hubo lesionados",
    )
    positive = (
        "si hubo",
        "hubo lesionados",
        "hay lesionados",
        "lesionados",
        "heridos",
        "lastimados",
        "ambulancia",
    )
    if any(_matches_whole_or_phrase(normalized, term) for term in negative):
        return _slot_match(
            slot="injuries",
            value=False,
            confidence=0.92 if contextual else 0.86,
            status=SlotStatus.ANSWERED,
            evidence=normalized,
            reason="injuries_denied",
        )
    if any(term in normalized for term in positive):
        return _slot_match(
            slot="injuries",
            value=True,
            confidence=0.9,
            status=SlotStatus.ANSWERED,
            evidence=normalized,
            reason="injuries_affirmed",
        )
    return None


def _match_user_role(
    normalized: str,
    *,
    contextual: bool,
    pending_question: Mapping[str, Any] | None,
) -> Dict[str, Any] | None:
    if _is_uncertain(normalized):
        return _slot_match(
            slot="user_role",
            value="unknown",
            confidence=0.45,
            status=SlotStatus.PARTIALLY_FILLED,
            evidence=normalized,
            reason="user_uncertain_about_role",
            close=False,
        )
    insured_terms = (
        "soy asegurado",
        "soy asegurada",
        "asegurado",
        "asegurada",
        "cliente",
        "soy cliente",
        "mi poliza",
        "mi seguro",
        "galicia",
    )
    third_party_terms = (
        "soy tercero",
        "soy tercera",
        "tercero damnificado",
        "tercera damnificada",
        "damnificado",
        "damnificada",
        "no soy asegurado",
        "no soy asegurada",
    )
    if any(term in normalized for term in third_party_terms):
        return _slot_match(
            slot="user_role",
            value="third_party",
            confidence=0.9,
            status=SlotStatus.ANSWERED,
            evidence=normalized,
            reason="user_role_third_party",
        )
    if any(term in normalized for term in insured_terms):
        return _slot_match(
            slot="user_role",
            value="insured",
            confidence=0.9,
            status=SlotStatus.ANSWERED,
            evidence=normalized,
            reason="user_role_insured",
        )
    prompt = str((pending_question or {}).get("prompt") or "")
    if contextual and normalized.strip(" .!?") in {"si", "sí", "sip", "claro", "correcto"} and "asegurado" in normalize_text(prompt):
        return _slot_match(
            slot="user_role",
            value="insured",
            confidence=0.74,
            status=SlotStatus.ANSWERED,
            evidence=normalized,
            reason="contextual_affirmation_to_user_role_question",
        )
    return None


GENERIC_SLOT_MATCH_CONTRACT = "generic_contextual_slot_answer"

# ACA-305D-RC1 section 5/13: this is the only slot matcher with no relevance
# check -- any non-empty, non-"uncertain" text qualifies. The confidence it
# reports (0.5) does not vary with content, so a floor strictly above it
# (rather than a content-derived score) is what actually gates acceptance.
# See _clears_generic_slot_confidence_floor, the single point both
# `_looks_like_pending_answer` and `resolve_pending_slot_answers` consult
# (ACA-305D-RC1 section 8: one shared matching function, one shared fix).
GENERIC_SLOT_MATCH_CONFIDENCE_FLOOR = 0.6


def _match_generic_slot(slot_name: str, normalized: str, *, contextual: bool) -> Dict[str, Any] | None:
    if not contextual or _is_uncertain(normalized) or len(normalized) < 2:
        return None
    return _slot_match(
        slot=slot_name,
        value=normalized,
        confidence=0.5,
        status=SlotStatus.PARTIALLY_FILLED,
        evidence=normalized,
        reason=GENERIC_SLOT_MATCH_CONTRACT,
        close=False,
    )


def _clears_generic_slot_confidence_floor(match: Mapping[str, Any] | None) -> bool:
    """True for every match except a generic contextual match below the
    confidence floor. Matches from `_match_injuries`/`_match_user_role`
    (explicit term lists, or their own contextual branches) are untouched --
    this only gates the no-relevance-check generic fallback."""

    if match is None:
        return False
    if str(match.get("reason") or "") != GENERIC_SLOT_MATCH_CONTRACT:
        return True
    return float(match.get("confidence") or 0.0) >= GENERIC_SLOT_MATCH_CONFIDENCE_FLOOR


def _slot_match(
    *,
    slot: str,
    value: Any,
    confidence: float,
    status: str,
    evidence: str,
    reason: str,
    close: bool = True,
) -> Dict[str, Any]:
    return {
        "slot": slot,
        "value": value,
        "confidence": confidence,
        "target_status": status,
        "evidence": {
            "normalized_message": evidence,
            "source": "user_message",
        },
        "reason": reason,
        "close": close,
    }


def _slot_transition(
    *,
    slot: Mapping[str, Any],
    match: Mapping[str, Any],
    pending_questions: Sequence[Mapping[str, Any]],
    active_mission: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    from_status = str(slot.get("status") or SlotStatus.PENDING)
    to_status = str(match.get("target_status") or SlotStatus.ANSWERED)
    if to_status not in SLOT_LIFECYCLE.get(from_status, ()) and from_status != to_status:
        to_status = SlotStatus.PARTIALLY_FILLED
    closed = bool(match.get("close")) and to_status in SLOT_CLOSED_STATUSES
    question = _question_for_slot(str(match["slot"]), pending_questions)
    slot_after = dict(slot)
    slot_after.update(
        {
            "name": str(match["slot"]),
            "status": to_status,
            "value": deepcopy(match.get("value")),
            "confidence": float(match.get("confidence") or 0.0),
            "evidence": deepcopy(match.get("evidence") or {}),
            "updated_by": "conversation_state",
        }
    )
    if closed:
        slot_after["closed_by"] = "pending_question_resolution"
    return {
        "slot": str(match["slot"]),
        "component": "conversation_state",
        "from_status": from_status,
        "to_status": to_status,
        "value": deepcopy(match.get("value")),
        "confidence": float(match.get("confidence") or 0.0),
        "evidence": deepcopy(match.get("evidence") or {}),
        "reason": str(match.get("reason") or "slot_answer_detected"),
        "mission_type": (active_mission or {}).get("type"),
        "question_resolved": dict(question or {}),
        "closed": closed,
        "slot_after": slot_after,
    }


def _repeated_slot_answer(normalized: str, slots: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any] | None:
    for slot_name, slot in slots.items():
        if slot.get("status") not in SLOT_CLOSED_STATUSES:
            continue
        match = _match_slot_answer(str(slot_name), normalized, contextual=False)
        if match is None:
            continue
        if match.get("value") != slot.get("value"):
            continue
        return {
            "slot": str(slot_name),
            "component": "conversation_state",
            "from_status": slot.get("status"),
            "to_status": slot.get("status"),
            "value": deepcopy(slot.get("value")),
            "confidence": float(match.get("confidence") or 0.0),
            "evidence": deepcopy(match.get("evidence") or {}),
            "reason": "repeated_answer_for_closed_slot",
            "mission_type": None,
            "question_resolved": {},
            "closed": False,
            "repeated": True,
        }
    return None


def _mission_with_slots(active_mission: Mapping[str, Any] | None, slots: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any] | None:
    if not active_mission:
        return None
    mission = dict(active_mission)
    mission["slots"] = {name: dict(slot) for name, slot in slots.items()}
    missing = [
        name
        for name, slot in slots.items()
        if slot.get("status") in {SlotStatus.PENDING, SlotStatus.PARTIALLY_FILLED}
    ]
    mission["missing"] = missing
    blockers = []
    for blocker in mission.get("blockers") or []:
        blocker_text = str(blocker)
        slot_name = blocker_text.removesuffix("_unknown")
        if slot_name in missing:
            blockers.append(blocker_text)
    mission["blockers"] = blockers
    return mission


def _question_for_slot(slot_name: str, pending_questions: Sequence[Mapping[str, Any]]) -> Dict[str, Any] | None:
    for question in pending_questions:
        if question.get("slot") == slot_name:
            return dict(question)
    return None


def _slot_priority(slot_name: str) -> int:
    return {"injuries": 10, "user_role": 20}.get(slot_name, 100)


def _is_uncertain(normalized: str) -> bool:
    return any(
        term in normalized
        for term in (
            "no se",
            "no estoy seguro",
            "no estoy segura",
            "creo que no",
            "creo que si",
            "tal vez",
            "quizas",
            "puede ser",
        )
    )


def _matches_whole_or_phrase(normalized: str, term: str) -> bool:
    stripped = normalized.strip(" .!?")
    return stripped == term or term in normalized


def _append_unique(values: tuple[str, ...], *extra: str) -> tuple[str, ...]:
    ordered = list(values)
    for value in extra:
        if value and value not in ordered:
            ordered.append(value)
    return tuple(ordered)


def _mapping_or_none(value: Any) -> Dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _default_component_for_field(field_name: str) -> str:
    if field_name == "active_mission":
        return "mission_manager"
    if field_name in {"confirmed_facts", "active_hypotheses"}:
        return "kernel"
    if field_name == "relevant_evidence":
        return "tool_engine"
    if field_name in {"relevant_context", "derived_state"}:
        return "context_manager"
    if field_name in {"conversation_id", "turn_count"}:
        return "conversation_manager"
    if field_name == "product_state":
        return "public_layer"
    return "conversation_state"


def _focus_from_cognitive_state(state: Any, active_mission: Mapping[str, Any] | None) -> Dict[str, Any]:
    focus: Dict[str, Any] = {}
    if active_mission:
        mission_type = active_mission.get("type")
        if mission_type:
            focus["active_mission_type"] = mission_type
            focus["source"] = "active_mission"
        concept_key = active_mission.get("concept_key")
        if concept_key:
            focus["active_concept"] = concept_key
    intent_match = getattr(state, "intent_match", None)
    if isinstance(intent_match, Mapping) and intent_match.get("intent"):
        focus.setdefault("last_intent", intent_match.get("intent"))
    return focus


def _focus_from_public_state(state: Any, semantic: Mapping[str, Any]) -> Dict[str, Any]:
    focus: Dict[str, Any] = {}
    topic = semantic.get("topic") or getattr(state, "active_topic", None)
    if topic:
        focus["active_topic"] = topic
    claim_type = (semantic.get("entities") or {}).get("claim_type") if isinstance(semantic.get("entities"), Mapping) else None
    claim_type = claim_type or getattr(state, "active_claim_type", None)
    if claim_type:
        focus["active_claim_type"] = claim_type
    case_id = (semantic.get("entities") or {}).get("case_id") if isinstance(semantic.get("entities"), Mapping) else None
    case_id = case_id or getattr(state, "active_case_id", None)
    if case_id:
        focus["active_case_id"] = str(case_id)
    if focus:
        focus["source"] = "public_conversation_state"
    return focus


def _focus_from_context_bundle(context: Mapping[str, Any], mission: Mapping[str, Any] | None) -> Dict[str, Any]:
    focus: Dict[str, Any] = {}
    if mission and mission.get("type"):
        focus["active_mission_type"] = mission["type"]
        focus["source"] = "context_bundle.mission"
    domain = context.get("domain_context")
    if isinstance(domain, Mapping) and domain.get("domain"):
        focus["domain"] = domain["domain"]
    return focus


def _topic_stack_from_focus(focus: Mapping[str, Any]) -> list[Dict[str, Any]]:
    stack = []
    for key in ("active_topic", "active_claim_type", "active_case_id", "active_mission_type", "active_concept"):
        if focus.get(key):
            stack.append(_normalize_topic({"type": key, "value": focus[key], "status": TopicStatus.ACTIVE}))
    return stack


def _topic_stack_from_cognitive_facts(
    facts: Mapping[str, Any],
    *,
    focus: Mapping[str, Any],
    active_mission: Mapping[str, Any] | None = None,
    turn_count: int = 0,
) -> list[Dict[str, Any]]:
    projection = facts.get("conversation_topic_stack")
    if isinstance(projection, Mapping):
        topics = projection.get("topics") or projection.get("current_stack") or projection.get("topic_stack")
        if isinstance(topics, Sequence) and not isinstance(topics, (str, bytes)):
            return [
                _normalize_topic(topic)
                for topic in topics
                if isinstance(topic, Mapping)
            ]
    active_topic = facts.get("conversation_active_topic")
    if isinstance(active_topic, Mapping):
        return [_normalize_topic(active_topic)]
    if active_mission and active_mission.get("type"):
        mission_type = str(active_mission.get("type"))
        return [
            _normalize_topic(
                {
                    "contract": "conversation_topic.v1",
                    "id": f"mission:{mission_type}",
                    "type": mission_type,
                    "mission_type": mission_type,
                    "mission_goal": active_mission.get("goal"),
                    "priority": 80,
                    "status": TopicStatus.ACTIVE,
                    "created_turn": int(turn_count),
                    "last_active_turn": int(turn_count),
                    "associated_facts": {},
                    "associated_slots": {},
                    "summary": active_mission.get("goal") or mission_type,
                }
            )
        ]
    return _topic_stack_from_focus(focus)


def _slot_with_defaults(
    name: str,
    slot: Dict[str, Any],
    *,
    source: str,
    mission_type: str,
) -> Dict[str, Any]:
    slot.setdefault("name", name)
    slot.setdefault("status", SlotStatus.PENDING)
    slot.setdefault("value", None)
    slot.setdefault("source", source)
    slot.setdefault("reason", _slot_reason(name))
    slot.setdefault("priority", _slot_priority(name))
    slot.setdefault("prompt", _slot_prompt(name))
    slot.setdefault("close_conditions", _slot_close_conditions(name))
    slot.setdefault("mission_type", mission_type)
    return slot


def _slot_reason(name: str) -> str:
    return {
        "injuries": "Lesionados cambia urgencia, derivacion y circuito del siniestro.",
        "user_role": "El rol del usuario define canal y tipo de orientacion.",
    }.get(name, "Informacion pendiente necesaria para continuar.")


def _slot_prompt(name: str) -> str:
    return {
        "injuries": "¿Hubo lesionados?",
        "user_role": "¿Sos asegurado de Galicia o sos tercero damnificado?",
    }.get(name, f"Necesito confirmar {name}.")


def _slot_close_conditions(name: str) -> list[str]:
    return [
        f"{name}.status in answered|confirmed|invalidated|refuted",
        f"{name}.value is not null",
    ]


def _slots_from_mission(mission: Mapping[str, Any] | None, *, source: str) -> Dict[str, Dict[str, Any]]:
    if not mission:
        return {}
    missing = mission.get("missing") or ()
    blockers = set(mission.get("blockers") or ())
    mission_type = str(mission.get("type") or "")
    slots = _slots_from_missing(missing, source=source)
    mission_slots = mission.get("slots")
    if isinstance(mission_slots, Mapping):
        for name, slot in mission_slots.items():
            if isinstance(slot, Mapping):
                slots[str(name)] = _slot_with_defaults(str(name), dict(slot), source=source, mission_type=mission_type)
    for name, slot in slots.items():
        if f"{name}_unknown" in blockers:
            slot["blocker"] = f"{name}_unknown"
        slot.setdefault("mission_type", mission_type)
    return slots


def _slots_from_missing(values: Sequence[Any], *, source: str) -> Dict[str, Dict[str, Any]]:
    slots: Dict[str, Dict[str, Any]] = {}
    for value in values:
        name = str(value).strip()
        if not name:
            continue
        slots[name] = {
            "name": name,
            "status": SlotStatus.PENDING,
            "value": None,
            "source": source,
            "reason": _slot_reason(name),
            "priority": _slot_priority(name),
            "prompt": _slot_prompt(name),
            "close_conditions": _slot_close_conditions(name),
        }
    return slots


def _pending_questions_from_slots(slots: Mapping[str, Mapping[str, Any]], *, source: str) -> list[Dict[str, Any]]:
    return [
        {
            "id": f"{slot.get('mission_type') or 'conversation'}:{name}",
            "slot": name,
            "status": SlotStatus.PENDING,
            "reason": slot.get("reason") or _slot_reason(name),
            "priority": int(slot.get("priority", _slot_priority(name)) or _slot_priority(name)),
            "mission_type": slot.get("mission_type"),
            "prompt": slot.get("prompt") or _slot_prompt(name),
            "close_conditions": list(slot.get("close_conditions") or _slot_close_conditions(name)),
            "source": source,
        }
        for name, slot in slots.items()
        if slot.get("status") in {SlotStatus.PENDING, SlotStatus.PARTIALLY_FILLED}
    ]


def _conversation_facts_from_cognitive_state(state: Any) -> Dict[str, Any]:
    facts: Dict[str, Any] = {}
    raw_facts = dict(getattr(state, "facts", {}) or {})
    structured_facts = {
        str(key)[5:]: deepcopy(value)
        for key, value in raw_facts.items()
        if str(key).startswith("fact.")
        and isinstance(value, Mapping)
        and value.get("contract") == "conversational_fact.v1"
    }
    for key, value in raw_facts.items():
        if _is_runtime_projection_key(str(key)):
            continue
        fact_key = str(key)
        facts[fact_key] = deepcopy(structured_facts.get(fact_key, value))
    for key, value in structured_facts.items():
        facts.setdefault(key, deepcopy(value))
    for key, value in dict(getattr(state, "entities", {}) or {}).items():
        facts[f"entity.{key}"] = deepcopy(value)
    return facts


def _is_runtime_projection_key(key: str) -> bool:
    return (
        key.startswith("zero_cost_")
        or key.startswith("runtime_")
        or key.startswith("fact.")
        or key
        in {
            "conversation_state_runtime",
            "conversation_act",
            "conversation_act_recognition",
            "conversation_goal",
            "conversation_intent_model",
            "conversation_information_gain_plan",
            "conversation_plan",
            "conversation_response_plan",
            "conversation_fulfillment",
            "conversation_active_topic",
            "conversation_topic_stack",
            "execution_step_outcomes",
            "conversation_slot_resolution",
            "conversation_fact_assimilation",
            "conversation_fact_revision",
            "conversation_mission_advancement",
        }
    )


def _facts_from_sequence(values: Sequence[Any]) -> Dict[str, Any]:
    facts: Dict[str, Any] = {}
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if ":" in text:
            key, fact_value = text.split(":", 1)
            facts[key.strip()] = fact_value.strip()
        else:
            facts[text] = True
    return facts


def _goals_from_cognitive_state(state: Any, active_mission: Mapping[str, Any] | None) -> list[Dict[str, Any]]:
    goals = []
    if getattr(state, "goal", None):
        goals.append({"name": getattr(state, "goal"), "status": "active", "source": "CognitiveState.goal"})
    goals.extend(_goals_from_mission(active_mission))
    return goals


def _goals_from_mission(mission: Mapping[str, Any] | None) -> list[Dict[str, Any]]:
    if not mission or not mission.get("goal"):
        return []
    return [
        {
            "name": mission["goal"],
            "status": mission.get("status", "active"),
            "source": "active_mission",
        }
    ]


def _goals_from_public_state(state: Any, semantic: Mapping[str, Any]) -> list[Dict[str, Any]]:
    goal = semantic.get("user_goal") or getattr(state, "active_goal", None)
    if not goal:
        return []
    return [{"name": goal, "status": "active", "source": "public_conversation_state"}]


def _last_act_from_cognitive_state(state: Any) -> Dict[str, Any]:
    facts = dict(getattr(state, "facts", {}) or {})
    conversation_act = facts.get("conversation_act")
    if isinstance(conversation_act, Mapping) and conversation_act.get("act"):
        return deepcopy(dict(conversation_act))
    intent_match = getattr(state, "intent_match", None)
    if isinstance(intent_match, Mapping):
        return {
            "type": intent_match.get("intent"),
            "confidence": intent_match.get("confidence"),
            "source": "IntentMatch",
        }
    return {}


def _last_act_from_public_state(state: Any, semantic: Mapping[str, Any]) -> Dict[str, Any]:
    if semantic:
        return {
            "type": semantic.get("intent"),
            "category": getattr(state, "last_category", None),
            "confidence": semantic.get("confidence"),
            "source": "SemanticParse",
        }
    if getattr(state, "last_category", None):
        return {"category": getattr(state, "last_category"), "source": "PublicConversationState.last_category"}
    return {}


def _strategy_from_planner(planner: Mapping[str, Any], next_action_suggested: Any) -> Dict[str, Any]:
    if planner:
        return {
            "next_action": planner.get("next_action"),
            "strategy": planner.get("strategy"),
            "needs_clarification": planner.get("needs_clarification"),
            "source": "PlannerDecision",
        }
    if next_action_suggested:
        return {"next_action": next_action_suggested, "source": "PublicConversationState.next_action_suggested"}
    return {}


def _product_state_from_public_state(state: Any) -> Dict[str, Any]:
    return {
        "last_category": getattr(state, "last_category", None),
        "fallback_count": int(getattr(state, "fallback_count", 0) or 0),
        "confusion_count": int(getattr(state, "confusion_count", 0) or 0),
        "frustration_count": int(getattr(state, "frustration_count", 0) or 0),
        "last_response_signature": getattr(state, "last_response_signature", None),
        "control_state": dict(getattr(state, "control_state", None) or {}),
    }


def _derived_state_from_cognitive_state(state: Any, context_bundle: Mapping[str, Any] | None) -> Dict[str, Any]:
    derived: Dict[str, Any] = {}
    for key in (
        "zero_cost_action_plan",
        "zero_cost_execution_flow",
        "zero_cost_execution_plan",
        "runtime_execution_engine",
        "conversation_act_recognition",
        "conversation_goal",
        "conversation_intent_model",
        "conversation_information_gain_plan",
        "conversation_plan",
        "conversation_response_plan",
        "conversation_fulfillment",
        "conversation_topic_stack",
        "conversation_slot_resolution",
        "conversation_fact_assimilation",
        "conversation_fact_revision",
        "conversation_mission_advancement",
    ):
        value = dict(getattr(state, "facts", {}) or {}).get(key)
        if value is not None:
            derived[
                {
                    "conversation_act_recognition": "conversation_act",
                    "conversation_goal": "conversation_goal",
                    "conversation_intent_model": "conversation_intent_model",
                    "conversation_information_gain_plan": "conversation_information_gain_plan",
                    "conversation_plan": "conversation_plan",
                    "conversation_response_plan": "conversation_response_plan",
                    "conversation_fulfillment": "conversation_fulfillment",
                    "conversation_topic_stack": "topic_stack",
                    "conversation_slot_resolution": "slot_resolution",
                    "conversation_fact_assimilation": "fact_assimilation",
                    "conversation_fact_revision": "fact_revision",
                    "conversation_mission_advancement": "mission_advancement",
                }.get(key, key)
            ] = deepcopy(value)
    if getattr(state, "policy_result", None):
        derived["policy_result"] = deepcopy(getattr(state, "policy_result"))
    if getattr(state, "memory_snapshot", None):
        derived["memory_snapshot"] = deepcopy(getattr(state, "memory_snapshot"))
    if context_bundle:
        derived["context_bundle"] = deepcopy(context_bundle)
    return derived


def _derived_state_from_public_projection(
    semantic: Mapping[str, Any],
    planner: Mapping[str, Any],
    supervisor: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    derived: Dict[str, Any] = {}
    if semantic:
        derived["semantic_parse"] = deepcopy(dict(semantic))
    if planner:
        derived["planner_decision"] = deepcopy(dict(planner))
    if supervisor:
        derived["supervisor_result"] = deepcopy(dict(supervisor))
    if context:
        derived["context_bundle"] = deepcopy(dict(context))
    return derived


def _relevant_context_from_context_bundle(context: Mapping[str, Any] | None) -> Dict[str, Any]:
    if not context:
        return {}
    relevant = {}
    for key in ("mission", "relevant_memory", "domain_context"):
        if key in context:
            relevant[key] = deepcopy(context[key])
    return relevant
