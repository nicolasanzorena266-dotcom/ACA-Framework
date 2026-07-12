from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from aca_core.text import normalize_text
from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.conversation_state import ConversationState


@dataclass(frozen=True)
class NarrativeResponse:
    response: str
    changed: bool
    reason: str


class NarrativeResponseComposer:
    """Final verbalization layer for already-decided cognitive state.

    The composer does not select intents, change plans, or mutate conversation
    state. It only turns existing cognitive projections into a more natural
    final response.
    """

    def compose(
        self,
        *,
        state: CognitiveState,
        event: Event,
        conversation_state: ConversationState | None = None,
    ) -> NarrativeResponse:
        original = str(state.response or "").strip()
        if not original:
            return NarrativeResponse(response=original, changed=False, reason="empty_response")
        if _should_preserve_response(state):
            cleaned = _clean_surface_template(original)
            return NarrativeResponse(
                response=cleaned,
                changed=cleaned != original,
                reason="preserved_specialized_response",
            )

        response_plan = _trace_payload(state, "conversation_response_plan", "plan")
        conversation_plan = _trace_payload(state, "conversation_plan", "plan")
        intent_model = _trace_payload(state, "conversation_intent_model", "model")
        fulfillment = _trace_payload(state, "conversation_fulfillment", "fulfillment")
        message = str(event.payload or "")
        normalized_message = normalize_text(message)

        composed = self._compose_repetition_repair(
            state=state,
            response_plan=response_plan,
            conversation_plan=conversation_plan,
            message=normalized_message,
        )
        if composed:
            return NarrativeResponse(response=composed, changed=composed != original, reason="repetition_repair")

        composed = self._compose_claim_status(
            state=state,
            message=normalized_message,
            response_plan=response_plan,
            conversation_plan=conversation_plan,
            intent_model=intent_model,
            fulfillment=fulfillment,
            conversation_state=conversation_state,
        )
        if composed:
            return NarrativeResponse(response=composed, changed=composed != original, reason="claim_status_narrative")

        composed = self._repair_generic_template(
            state=state,
            original=original,
            response_plan=response_plan,
            message=normalized_message,
            conversation_state=conversation_state,
        )
        if composed:
            return NarrativeResponse(response=composed, changed=composed != original, reason="generic_template_repair")

        composed = _reformulate_planned_question_in_response(
            original,
            response_plan=response_plan,
            conversation_state=conversation_state,
        )
        if composed != original:
            return NarrativeResponse(response=composed, changed=True, reason="planned_question_reformulation")

        cleaned = _clean_surface_template(original)
        return NarrativeResponse(
            response=cleaned,
            changed=cleaned != original,
            reason="surface_cleanup" if cleaned != original else "unchanged",
        )

    def _compose_claim_status(
        self,
        *,
        state: CognitiveState,
        message: str,
        response_plan: Mapping[str, Any],
        conversation_plan: Mapping[str, Any],
        intent_model: Mapping[str, Any],
        fulfillment: Mapping[str, Any],
        conversation_state: ConversationState | None,
    ) -> str | None:
        primary_key = _primary_need_key(response_plan)
        if primary_key not in {"claim_report_status", "claim_status_or_payment"}:
            return None
        if "denuncia" not in message and "siniestro" not in message:
            return None

        pieces: list[str] = []
        delay = _delay_phrase(message)
        if delay:
            pieces.append(
                f"Entiendo. Si ya paso {delay} desde que cargaste la denuncia y todavia figura en tramite, corresponde revisar que esta demorando el avance del caso."
            )
        elif _mentions_no_contact(message):
            pieces.append(
                "Entiendo. Si la denuncia ya esta cargada y todavia no recibiste novedades, corresponde revisar si el caso quedo pendiente de contacto, documentacion u observaciones."
            )
        else:
            pieces.append(
                "Entiendo. Si la denuncia ya esta cargada, el siguiente paso es revisar si el tramite tiene observaciones o si quedo pendiente algun contacto."
            )

        if _mentions_vehicle_repair(message):
            pieces.append(
                "Sobre el auto, si necesitas repararlo, conviene conservar fotos, presupuesto y cualquier comprobante antes de moverlo para no perder evidencia del dano."
            )

        follow_up = _claim_status_follow_up_sentence(message)
        if follow_up:
            pieces.append(follow_up)
        question = _natural_question_from_response_plan(
            response_plan,
            conversation_state=conversation_state,
        )
        if question:
            pieces.append(question)

        return _clean_surface_template(" ".join(pieces))

    def _compose_repetition_repair(
        self,
        *,
        state: CognitiveState,
        response_plan: Mapping[str, Any],
        conversation_plan: Mapping[str, Any],
        message: str,
    ) -> str | None:
        if not _is_repetition_complaint(message):
            return None
        if (state.active_mission or {}).get("type") != "auto_claim_guidance":
            return None

        known = _known_fact_sentence(state)
        question = _next_pending_question(state, response_plan, conversation_plan)
        pieces = ["Tenes razon"]
        if known:
            pieces.append(f", ya tengo registrado que {known}.")
        else:
            pieces.append(", tomo lo que ya me contaste.")
        if question:
            pieces.append(" " + question)
        else:
            pieces.append(" Veamos entonces como seguimos con el estado de la denuncia.")
        return _clean_surface_template("".join(pieces))

    def _repair_generic_template(
        self,
        *,
        state: CognitiveState,
        original: str,
        response_plan: Mapping[str, Any],
        message: str,
        conversation_state: ConversationState | None,
    ) -> str | None:
        normalized_response = normalize_text(original)
        if not _looks_like_generic_template(normalized_response):
            return None
        primary_key = _primary_need_key(response_plan)
        if primary_key in {"claim_report_status", "claim_status_or_payment"} or (
            state.active_mission or {}
        ).get("type") == "auto_claim_guidance":
            question = _natural_question_from_response_plan(
                response_plan,
                conversation_state=conversation_state,
            )
            if question:
                return _clean_surface_template(f"Con lo que ya me contaste sobre la denuncia, {question}")
            return "Con lo que ya me contaste sobre la denuncia, revisemos el proximo paso del tramite."
        return None


def _trace_payload(state: CognitiveState, fact_key: str, payload_key: str) -> dict[str, Any]:
    trace = state.facts.get(fact_key)
    if not isinstance(trace, Mapping):
        return {}
    payload = trace.get(payload_key)
    if isinstance(payload, Mapping):
        return dict(payload)
    return dict(trace)


def _primary_need_key(response_plan: Mapping[str, Any]) -> str:
    primary = response_plan.get("primary_user_need")
    if isinstance(primary, Mapping):
        return str(primary.get("key") or "")
    return ""


def _natural_question_from_response_plan(
    response_plan: Mapping[str, Any],
    *,
    conversation_state: ConversationState | None = None,
) -> str:
    item = _required_information_item(response_plan)
    if not item:
        return ""
    return _natural_question_from_required_information(item, conversation_state=conversation_state)


def _required_information_item(response_plan: Mapping[str, Any]) -> Mapping[str, Any] | None:
    required = response_plan.get("required_information")
    if not isinstance(required, list) or not required:
        return None
    item = next((entry for entry in required if isinstance(entry, Mapping)), None)
    if not item:
        return None
    return item


def _natural_question_from_required_information(
    item: Mapping[str, Any],
    *,
    conversation_state: ConversationState | None = None,
    include_purpose: bool = True,
) -> str:
    slot = str(item.get("key") or item.get("slot") or "")
    question = str(item.get("question") or "").strip()
    purpose = str(item.get("purpose") or "").strip()
    if slot == "injuries" or "lesionado" in normalize_text(question):
        question = _question_variant(
            "injuries",
            conversation_state=conversation_state,
            default="Recordas si alguna persona resulto herida o necesito atencion medica despues del choque?",
        )
    elif slot == "user_role" or "asegurado" in normalize_text(question):
        question = _question_variant(
            "user_role",
            conversation_state=conversation_state,
            default="El seguro Galicia es tuyo o estas reclamando como tercero?",
        )
    elif slot == "claim_report_loaded" or "denuncia ya esta cargada" in normalize_text(question):
        question = _question_variant(
            "claim_report_loaded",
            conversation_state=conversation_state,
            default=question or "La denuncia ya esta cargada?",
        )
    elif slot == "documentation_available" or "documentacion" in normalize_text(question):
        question = _question_variant(
            "documentation_available",
            conversation_state=conversation_state,
            default=question,
        )
    if not question:
        return ""
    if include_purpose and purpose:
        return f"{question} Asi puedo {purpose}."
    return question


def _question_variant(
    slot: str,
    *,
    conversation_state: ConversationState | None,
    default: str,
) -> str:
    variants = {
        "injuries": (
            default,
            "Recordas si alguna persona resulto herida o necesito atencion medica, aunque sea una duda?",
            "Alguna persona resulto herida despues del choque o fue solo dano material?",
            "Recordas si alguna persona resulto herida y tuvo que recibir asistencia medica?",
            "Despues del choque, alguna persona resulto herida o solo hubo danos en los vehiculos?",
        ),
        "user_role": (
            default,
            "Para ubicar el canal correcto, vos sos asegurado de Galicia o tercero damnificado?",
            "El tramite corresponde a tu poliza de Galicia o estas reclamando como tercero?",
            "Vos tenes el seguro en Galicia o el reclamo es contra otra cobertura?",
            "La denuncia la haces como asegurado de Galicia o como tercero afectado?",
        ),
        "claim_report_loaded": (
            default,
            "Para saber si hay que completarla o revisar observaciones, la denuncia ya esta cargada?",
            "Tenes confirmacion de que la denuncia ya esta cargada en la app?",
            "La denuncia ya esta cargada correctamente segun la app?",
            "Llegaste a finalizar la carga: la denuncia ya esta cargada o quedo algun paso pendiente?",
            "El tramite muestra que la denuncia ya esta cargada o todavia aparece pendiente?",
            "Pudiste completar todo hasta que la denuncia ya esta cargada en la app?",
            "Te quedo algun comprobante que confirme que la denuncia ya esta cargada?",
        ),
        "documentation_available": (
            default,
            "Tenes toda la documentacion, incluyendo fotos, presupuesto o lo que te hayan pedido?",
            "Tenes toda la documentacion que acompana la denuncia, como fotos o presupuesto?",
            "Tenes toda la documentacion o falta cargar algun documento, foto o comprobante?",
            "Tenes toda la documentacion del caso completa o quedo algo pendiente?",
        ),
    }.get(slot, (default,))
    index = 0
    if conversation_state is not None and conversation_state.turn_count > 1:
        index = (conversation_state.turn_count - 1) % len(variants)
    return variants[index]


def _reformulate_planned_question_in_response(
    response: str,
    *,
    response_plan: Mapping[str, Any],
    conversation_state: ConversationState | None,
) -> str:
    if conversation_state is None or conversation_state.turn_count <= 1:
        return response
    item = _required_information_item(response_plan)
    if not item:
        return response
    planned = str(item.get("question") or "").strip()
    natural = _natural_question_from_required_information(
        item,
        conversation_state=conversation_state,
        include_purpose=False,
    )
    if not planned or not natural or planned == natural:
        return response
    normalized_response = normalize_text(response)
    normalized_planned = normalize_text(planned)
    if normalized_planned not in normalized_response:
        return response
    for candidate in _question_text_candidates(planned):
        if candidate in response:
            return _clean_surface_template(response.replace(candidate, natural, 1))
    return response


def _question_text_candidates(question: str) -> tuple[str, ...]:
    stripped = question.strip()
    normalized = normalize_text(stripped)
    candidates = {stripped}
    if normalized != stripped:
        candidates.add(normalized)
    candidates.add(stripped.replace("\u00bf", ""))
    candidates.add(normalized.replace("\u00bf", ""))
    return tuple(candidate for candidate in candidates if candidate)


def _next_pending_question(
    state: CognitiveState,
    response_plan: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
) -> str:
    active = conversation_plan.get("active_plan")
    current_step = active.get("current_step") if isinstance(active, Mapping) else {}
    slot = str((current_step or {}).get("slot") or "")
    if slot == "user_role":
        return "Para seguir con el estado de la denuncia, me falta confirmar si el seguro Galicia es tuyo o si estas reclamando como tercero."
    if slot == "injuries":
        return "Para seguir con el estado de la denuncia, me falta confirmar si alguna persona resulto herida o necesito atencion medica."
    mission = state.active_mission or {}
    next_act = str(mission.get("next_act") or "")
    if next_act == "ask_user_role":
        return "Para seguir con el estado de la denuncia, me falta confirmar si el seguro Galicia es tuyo o si estas reclamando como tercero."
    if next_act == "ask_injuries":
        return "Para seguir con el estado de la denuncia, me falta confirmar si alguna persona resulto herida o necesito atencion medica."
    return _natural_question_from_response_plan(response_plan)


def _known_fact_sentence(state: CognitiveState) -> str:
    facts = dict(state.facts)
    mission = state.active_mission or {}
    mission_facts = mission.get("facts")
    if isinstance(mission_facts, Mapping):
        for key, value in mission_facts.items():
            if key not in facts:
                facts[key] = value.get("value") if isinstance(value, Mapping) else value
    known = []
    if facts.get("injuries") is False:
        known.append("no hubo lesionados")
    elif facts.get("injuries") is True:
        known.append("hubo lesionados")
    if facts.get("user_role") == "insured":
        known.append("sos asegurado")
    elif facts.get("user_role") == "third_party":
        known.append("sos tercero")
    if facts.get("claim_report_loaded") is True:
        known.append("la denuncia esta cargada")
    elif facts.get("claim_report_loaded") is False:
        known.append("la denuncia todavia no esta cargada")
    if facts.get("documentation_available") is True:
        known.append("tenes la documentacion")
    elif facts.get("documentation_available") is False:
        known.append("falta documentacion")
    return ", ".join(known)


def _delay_phrase(message: str) -> str:
    if "una semana" in message or "1 semana" in message:
        return "una semana"
    if "varios dias" in message or "unos dias" in message:
        return "varios dias"
    if "48" in message:
        return "mas de 48 horas habiles"
    return ""


def _mentions_no_contact(message: str) -> bool:
    return any(
        marker in message
        for marker in (
            "nadie me escribio",
            "nadie me contacto",
            "no me escribieron",
            "no me contactaron",
            "sin novedades",
            "no tengo novedades",
        )
    )


def _mentions_vehicle_repair(message: str) -> bool:
    return ("auto" in message or "vehiculo" in message) and any(
        marker in message for marker in ("reparar", "arreglar", "taller", "reparacion")
    )


def _claim_status_follow_up_sentence(message: str) -> str:
    if _mentions_no_contact(message):
        return "Tambien conviene mirar si desde la carga no hubo ningun contacto o si aparecio alguna observacion en la app."
    if "tramite" in message or "en tramite" in message:
        return "Tambien conviene revisar si hubo algun contacto, observacion o pedido pendiente desde la carga."
    return ""


def _is_repetition_complaint(message: str) -> bool:
    return any(
        marker in message
        for marker in (
            "ya te lo dije",
            "ya lo dije",
            "ya te dije",
            "ya dije eso",
            "ya me preguntaste",
        )
    )


def _looks_like_generic_template(response: str) -> bool:
    return any(
        marker in response
        for marker in (
            "te puedo orientar paso a paso",
            "nombrame el tramite",
            "contame que parte quedo trabada",
            "te oriento con el tramite",
        )
    )


def _should_preserve_response(state: CognitiveState) -> bool:
    execution_plan = state.facts.get("zero_cost_execution_plan")
    flow = execution_plan.get("flow") if isinstance(execution_plan, Mapping) else None
    if flow == "knowledge_lookup":
        return True
    if state.tool_evidence:
        return True
    if state.selected_program in {"greeting", "knowledge_lookup"}:
        return True
    return False


def _clean_surface_template(response: str) -> str:
    cleaned = str(response or "").strip()
    replacements = {
        "Te oriento. ": "",
        "Te oriento con el tramite. ": "",
        "Te oriento con el tr\u00e1mite. ": "",
        "Avancemos. ": "",
        "avancemos. ": "",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return " ".join(cleaned.split())
