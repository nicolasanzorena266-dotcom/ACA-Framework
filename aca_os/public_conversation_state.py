from __future__ import annotations

import unicodedata
from dataclasses import dataclass, replace
from typing import Any, Mapping


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
        }


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
) -> PublicConversationState:
    normalized = _norm(message)
    readable = _readable_norm(message)
    case_id = str(entities.get("case_id") or state.active_case_id or "") or None
    topic = state.active_topic
    goal = state.active_goal
    claim_type = state.active_claim_type

    if case_id:
        topic = "ticket"
        goal = "consultar_estado_o_seguimiento"

    detected_claim = _detect_claim_type(readable)
    if detected_claim:
        claim_type = detected_claim
        topic = "siniestro"
        goal = "orientar_siniestro"

    if _is_capability_question(readable):
        topic = topic or "capacidades"
        goal = goal or "explicar_capacidades"

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
    )
    _STATES[updated.conversation_id] = updated
    return updated


def _detect_claim_type(normalized: str) -> str | None:
    if any(word in normalized for word in ["choque", "colision", "colisión", "me chocaron", "accidente"]):
        return "choque"
    if any(word in normalized for word in ["cristal", "vidrio", "parabrisas", "luneta"]):
        return "cristales"
    if any(word in normalized for word in ["robo", "robaron", "rueda", "bateria", "batería", "estereo", "estéreo"]):
        return "robo parcial"
    if "franqui" in normalized or "franquisia" in normalized:
        return "franquicia"
    return None


def _is_confusion_or_short_reply(normalized: str) -> bool:
    return normalized.strip(" .!?¿¡") in {"eh", "ehh", "que", "qué", "bueno", "bue", "bueh", "ok", "okay", "y", "aja", "ajá"}


def _is_frustrated(normalized: str) -> bool:
    return any(phrase in normalized for phrase in ["bue", "no sirve", "inutil", "inútil", "solo podes", "solo podés", "no entendes", "no entendés", "no tenes ia", "no tenés ia", "no estas siendo", "ya me dijiste", "no ayuda", "mostrame"])


def _is_capability_question(normalized: str) -> bool:
    compact = normalized.replace("¿", "").replace("?", "")
    return any(phrase in compact for phrase in ["que podes hacer", "qué podés hacer", "que podés hacer", "que puedes hacer", "podes hacer algo", "podés hacer algo", "que haces", "qué haces"])


def _readable_norm(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value.lower()) if unicodedata.category(ch) != "Mn").strip()


def _norm(value: str) -> str:
    return value.lower().strip()
