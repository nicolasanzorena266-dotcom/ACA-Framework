from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping

from aca_core.text import normalize_search_text, normalize_text

@dataclass(frozen=True)
class PublicConversationState:
    """Small public conversation state for the hosted demo.

    This is not the full CSM implementation. It is the public-demo working
    memory used to keep the representative answer coherent across turns while
    the deterministic runtime remains the decision source.
    """

    conversation_id: str
    turn_count: int = 0
    active_goal: str | None = None
    active_topic: str | None = None
    active_case_id: str | None = None
    active_claim_type: str | None = None
    last_category: str | None = None
    fallback_count: int = 0
    confusion_count: int = 0
    frustration_count: int = 0
    known_facts: tuple[str, ...] = ()
    missing_facts: tuple[str, ...] = ()
    interaction_signals: dict[str, object] | None = None
    control_state: dict[str, object] | None = None
    next_action_suggested: str | None = None
    last_response_signature: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "turn_count": self.turn_count,
            "active_goal": self.active_goal,
            "active_topic": self.active_topic,
            "active_case_id": self.active_case_id,
            "active_claim_type": self.active_claim_type,
            "last_category": self.last_category,
            "fallback_count": self.fallback_count,
            "confusion_count": self.confusion_count,
            "frustration_count": self.frustration_count,
            "known_facts": list(self.known_facts),
            "missing_facts": list(self.missing_facts),
            "interaction_signals": dict(self.interaction_signals or {}),
            "control_state": dict(self.control_state or {}),
            "next_action_suggested": self.next_action_suggested,
            "last_response_signature": self.last_response_signature,
        }

    def to_conversation_state(
        self,
        *,
        semantic_parse: Mapping[str, Any] | None = None,
        planner_decision: Mapping[str, Any] | None = None,
        supervisor_result: Mapping[str, Any] | None = None,
        context_bundle: Mapping[str, Any] | None = None,
    ):
        from aca_os.conversation_state import ConversationState

        return ConversationState.from_public_state(
            self,
            semantic_parse=semantic_parse,
            planner_decision=planner_decision,
            supervisor_result=supervisor_result,
            context_bundle=context_bundle,
        )

    @classmethod
    def from_conversation_state(
        cls,
        conversation_state: Any,
        *,
        existing: "PublicConversationState | None" = None,
    ) -> "PublicConversationState":
        """Build the public-demo view from the canonical conversation contract."""

        focus = dict(getattr(conversation_state, "focus", {}) or {})
        product = dict(getattr(conversation_state, "product_state", {}) or {})
        goals = list(getattr(conversation_state, "goals", []) or [])
        slots = dict(getattr(conversation_state, "slots", {}) or {})
        facts = dict(getattr(conversation_state, "confirmed_facts", {}) or {})
        strategy = dict(getattr(conversation_state, "conversational_strategy", {}) or {})
        signals = dict(getattr(conversation_state, "user_signals", {}) or {})
        last_act = dict(getattr(conversation_state, "last_conversational_act", {}) or {})
        base = existing or cls(conversation_id=str(getattr(conversation_state, "conversation_id", "public")))
        return replace(
            base,
            conversation_id=str(getattr(conversation_state, "conversation_id", base.conversation_id)),
            turn_count=int(getattr(conversation_state, "turn_count", base.turn_count) or 0),
            active_goal=_first_goal_name(goals) or base.active_goal,
            active_topic=focus.get("active_topic") or base.active_topic,
            active_case_id=focus.get("active_case_id") or base.active_case_id,
            active_claim_type=focus.get("active_claim_type") or base.active_claim_type,
            last_category=last_act.get("category") or product.get("last_category") or base.last_category,
            fallback_count=int(product.get("fallback_count", base.fallback_count) or 0),
            confusion_count=int(product.get("confusion_count", base.confusion_count) or 0),
            frustration_count=int(product.get("frustration_count", base.frustration_count) or 0),
            known_facts=tuple(_fact_tokens(facts)),
            missing_facts=tuple(name for name, slot in slots.items() if slot.get("status") == "pending"),
            interaction_signals=signals or base.interaction_signals,
            control_state=dict(product.get("control_state") or base.control_state or {}),
            next_action_suggested=strategy.get("next_action") or base.next_action_suggested,
            last_response_signature=product.get("last_response_signature") or base.last_response_signature,
        )


_STATES: dict[str, PublicConversationState] = {}


def get_public_conversation_state(conversation_id: str) -> PublicConversationState:
    key = conversation_id or "demo-domain-flow"
    state = _STATES.get(key)
    if state is None:
        state = PublicConversationState(conversation_id=key)
        _STATES[key] = state
    return state


def reset_public_conversation_state(conversation_id: str) -> PublicConversationState:
    key = conversation_id or "demo-domain-flow"
    state = PublicConversationState(conversation_id=key)
    _STATES[key] = state
    return state


def update_public_conversation_state(
    state: PublicConversationState,
    *,
    message: str,
    pack: Mapping[str, Any],
    intent: Mapping[str, Any],
    entities: Mapping[str, Any],
    answer_category: str,
    semantic_parse: Mapping[str, Any] | None = None,
    policy_decision: Mapping[str, Any] | None = None,
    next_action: str | None = None,
    response_text: str | None = None,
) -> PublicConversationState:
    readable = normalize_text(message)
    semantic = dict(semantic_parse or {})
    semantic_entities = dict(semantic.get("entities") or {})
    case_id = str(entities.get("case_id") or semantic_entities.get("case_id") or state.active_case_id or "") or None
    topic = state.active_topic
    goal = state.active_goal
    claim_type = state.active_claim_type

    if case_id:
        topic = "ticket"
        goal = "consultar_estado_o_seguimiento"

    detected_claim = semantic_entities.get("claim_type") or _detect_claim_type(readable)
    if detected_claim:
        claim_type = detected_claim
        topic = "siniestro"
        goal = "orientar_siniestro"

    if semantic.get("topic"):
        topic = str(semantic.get("topic"))
    if semantic.get("user_goal"):
        goal = str(semantic.get("user_goal"))
    if _is_capability_question(readable):
        topic = topic or "capacidades"
        goal = goal or "explicar_capacidades"

    known_facts = tuple(dict.fromkeys([*state.known_facts, *(semantic.get("known_facts") or [])]))
    missing_facts = tuple(dict.fromkeys([*(semantic.get("missing_facts") or [])]))
    interaction_signals = dict(semantic.get("signals") or state.interaction_signals or {})
    control_state = dict(policy_decision or state.control_state or {})
    response_signature = _signature(response_text) if response_text else state.last_response_signature

    fallback_count = state.fallback_count + 1 if answer_category == "fallback" else 0
    confusion_count = state.confusion_count + 1 if _is_confusion_or_short_reply(readable) else state.confusion_count
    frustration_count = state.frustration_count + 1 if _is_frustrated(readable) else state.frustration_count

    updated = replace(
        state,
        turn_count=state.turn_count + 1,
        active_goal=goal,
        active_topic=topic,
        active_case_id=case_id,
        active_claim_type=claim_type,
        last_category=answer_category,
        fallback_count=fallback_count,
        confusion_count=confusion_count,
        frustration_count=frustration_count,
        known_facts=known_facts,
        missing_facts=missing_facts,
        interaction_signals=interaction_signals,
        control_state=control_state,
        next_action_suggested=next_action,
        last_response_signature=response_signature,
    )
    _STATES[updated.conversation_id] = updated
    return updated


def _detect_claim_type(normalized: str) -> str | None:
    if any(word in normalized for word in ["choque", "colision", "colisiÃ³n", "me chocaron", "accidente"]):
        return "choque"
    if any(word in normalized for word in ["cristal", "vidrio", "parabrisas", "luneta"]):
        return "cristales"
    if any(word in normalized for word in ["robo", "robaron", "rueda", "bateria", "baterÃ­a", "estereo", "estÃ©reo"]):
        return "robo parcial"
    if "franqui" in normalized or "franquisia" in normalized:
        return "franquicia"
    return None


def _is_confusion_or_short_reply(normalized: str) -> bool:
    return normalized.strip(" .!?Â¿Â¡") in {"eh", "ehh", "que", "quÃ©", "bueno", "bue", "bueh", "ok", "okay", "y", "aja", "ajÃ¡"}


def _is_frustrated(normalized: str) -> bool:
    return any(phrase in normalized for phrase in ["bue", "no sirve", "inutil", "inÃºtil", "solo podes", "solo podÃ©s", "no entendes", "no entendÃ©s", "no tenes ia", "no tenÃ©s ia", "no estas siendo", "ya me dijiste", "no ayuda", "mostrame"])


def _is_capability_question(normalized: str) -> bool:
    compact = normalize_search_text(normalized)
    return any(phrase in compact for phrase in ["que podes hacer", "quÃ© podÃ©s hacer", "que podÃ©s hacer", "que puedes hacer", "podes hacer algo", "podÃ©s hacer algo", "que haces", "quÃ© haces"])


def _signature(value: str | None) -> str | None:
    if not value:
        return None
    words = normalize_text(value).split()
    return " ".join(words[:22])


def _first_goal_name(goals: list[Mapping[str, Any]]) -> str | None:
    for goal in goals:
        if isinstance(goal, Mapping) and goal.get("name"):
            return str(goal["name"])
    return None


def _fact_tokens(facts: Mapping[str, Any]) -> list[str]:
    tokens: list[str] = []
    for key, value in facts.items():
        if key.startswith("entity."):
            continue
        if value is True:
            tokens.append(str(key))
        else:
            tokens.append(f"{key}:{value}")
    return tokens
