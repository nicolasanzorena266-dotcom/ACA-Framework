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
            topic_stack=_topic_stack_from_focus(focus),
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
            "conversation_slot_resolution",
            "conversation_fact_assimilation",
            "conversation_fact_revision",
            "conversation_mission_advancement",
        ):
            if key in derived and key not in facts:
                facts[key] = deepcopy(derived[key])
        if self.last_conversational_act:
            facts["conversation_act"] = deepcopy(self.last_conversational_act)
        if "conversation_act" in derived:
            facts["conversation_act_recognition"] = deepcopy(derived["conversation_act"])
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

    slots = deepcopy(conversation_state.slots)
    pending_questions = [dict(question) for question in conversation_state.pending_questions]
    active_mission = deepcopy(conversation_state.active_mission) if conversation_state.active_mission else None
    confirmed_facts = deepcopy(conversation_state.confirmed_facts)
    derived_state = deepcopy(conversation_state.derived_state)
    resolutions: list[Dict[str, Any]] = []

    pending_slots = _ordered_pending_slot_names(slots, pending_questions)
    explicit_matches = _explicit_slot_matches(normalized, pending_slots)
    if not explicit_matches and pending_slots:
        contextual = _contextual_slot_match(normalized, pending_slots, pending_questions)
        if contextual:
            explicit_matches.append(contextual)

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

    if not resolutions:
        return conversation_state, []

    active_mission = _mission_with_slots(active_mission, slots)
    trace = {
        "contract": "slot_resolution_trace.v1",
        "component": "conversation_state",
        "message": str(message),
        "resolutions": [dict(resolution) for resolution in resolutions],
    }
    derived_state["slot_resolution"] = trace
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
    if _mentions_documentation_available(normalized):
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


def _is_generic_withdrawal(normalized: str) -> bool:
    stripped = normalized.strip(" .!?")
    return stripped in {
        "me confundi",
        "me equivoque",
        "perdon me confundi",
        "perdon, me confundi",
        "perdon me equivoque",
        "perdon, me equivoque",
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


def _match_generic_slot(slot_name: str, normalized: str, *, contextual: bool) -> Dict[str, Any] | None:
    if not contextual or _is_uncertain(normalized) or len(normalized) < 2:
        return None
    return _slot_match(
        slot=slot_name,
        value=normalized,
        confidence=0.5,
        status=SlotStatus.PARTIALLY_FILLED,
        evidence=normalized,
        reason="generic_contextual_slot_answer",
        close=False,
    )


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
            stack.append({"type": key, "value": focus[key], "status": "active"})
    return stack


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
        "conversation_slot_resolution",
        "conversation_fact_assimilation",
        "conversation_fact_revision",
        "conversation_mission_advancement",
    ):
        value = dict(getattr(state, "facts", {}) or {}).get(key)
        if value is not None:
            derived[
                {
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
