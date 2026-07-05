from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping

from aca_os.public_conversation_state import PublicConversationState


@dataclass(frozen=True)
class PublicReplyDecision:
    text: str
    category: str
    next_step: str | None = None


class AdaptiveReplyPolicy:
    """Conversation policy for the public Studio demo.

    The domain runtime still detects intent, entities and candidate route. This
    policy decides how that internal result should become a public-facing answer
    using the current conversation state. It is intentionally deterministic for
    the public demo: human outside, observable runtime inside.
    """

    def decide(
        self,
        *,
        message: str,
        pack: Mapping[str, Any],
        intent: Mapping[str, Any],
        flow: Mapping[str, Any],
        entities: Mapping[str, Any],
        state: PublicConversationState | None,
    ) -> PublicReplyDecision:
        del flow  # kept in the signature because the route belongs to the observable process
        text = normalize_public_text(message)
        compact = compact_text(message)
        case_id = str(entities.get("case_id") or (state.active_case_id if state else "") or "") or None
        intent_name = str(intent.get("name") or "consulta")
        domain = str(pack.get("domain") or "")

        if is_greeting(compact):
            return PublicReplyDecision(
                category="greeting",
                text=(
                    "Hola 😊 Soy ACA. Puedo orientarte sobre siniestros, documentación, plazos, franquicia, "
                    "cristales, robo parcial o mostrar cómo prepararía una consulta de ticket en esta demo. "
                    "No tengo conexión real a sistemas del cliente, así que no voy a inventar estados ni datos privados."
                ),
                next_step="Elegir un trámite, siniestro o ticket de demo.",
            )

        if is_identity_question(compact):
            return PublicReplyDecision(
                category="identity",
                text=(
                    "Soy ACA, un asistente de atención en versión demo 😊. Mi trabajo es entender qué necesitás, "
                    "mantener el contexto de la conversación y orientarte con la información disponible. Si algo requiere "
                    "consultar un sistema real, te lo digo claro en vez de inventarlo."
                ),
                next_step="Continuar con la consulta activa o pedir capacidades.",
            )

        if is_ai_question(compact):
            return PublicReplyDecision(
                category="ai_limit",
                text=(
                    "Tengo una capa conversacional para esta demo, pero no estoy conectado a una IA externa libre ni a los sistemas reales del cliente. "
                    "La lógica de ACA es otra: primero entiende la consulta, sostiene el contexto, decide qué puede hacer y después responde. "
                    "Lo que no puedo hacer es consultar un caso real o inventar datos. Si el dato no está disponible, te explico qué buscaría o qué paso conviene seguir."
                ),
                next_step="Continuar con una consulta concreta o abrir el proceso interno.",
            )

        if is_capability_question(compact):
            return capability_answer(state=state)

        if is_frustration(compact):
            contextual = contextual_answer(state=state, frustrated=True)
            if contextual is not None:
                return contextual
            return PublicReplyDecision(
                category="frustration_repair",
                text=(
                    "Sí, te entiendo: si repito una respuesta genérica, la demo no sirve. Puedo ayudarte mejor si lo llevamos a un caso concreto: "
                    "ticket, choque, cristales, robo parcial, franquicia, documentación, plazos o próximos pasos."
                ),
                next_step="Reformular con opciones concretas y no repetir fallback.",
            )

        if is_confusion_question(compact) or is_short_ack(compact):
            contextual = contextual_answer(state=state, frustrated=False)
            if contextual is not None:
                return contextual
            return PublicReplyDecision(
                category="clarification",
                text=(
                    "Me explico mejor: esta demo puede orientarte y mostrar cómo prepararía una gestión, pero no consulta bases reales. "
                    "Podés probar con un ticket, un choque, cristales, robo parcial, franquicia, documentación o plazos."
                ),
                next_step="Ofrecer una consulta concreta o explicar capacidades.",
            )

        claim = claim_answer(compact=compact, state=state)
        if claim is not None:
            return claim

        missing = entities.get("missing_required")
        if isinstance(missing, list) and missing:
            readable = ", ".join(str(item).replace("_", " ") for item in missing)
            return PublicReplyDecision(
                category="missing_information",
                text=(
                    f"Puedo ayudarte, pero para avanzar sin inventar me falta este dato: {readable}. "
                    "Pasámelo y continúo con la orientación."
                ),
                next_step="Pedir el dato faltante y volver a evaluar.",
            )

        if domain == "customer.support" and case_id:
            if "documentation" in intent_name:
                return PublicReplyDecision(
                    category="ticket_documentation",
                    text=(
                        f"Te cuento que en esta demo no tengo conexión real al sistema del cliente, así que no puedo ver la documentación verdadera del ticket {case_id}. "
                        "Lo que sí puedo hacer es mostrarte cómo interpretaría la consulta: detecto que querés revisar documentación pendiente y prepararía la búsqueda de archivos faltantes, responsable y próximo paso 😊"
                    ),
                    next_step=f"Preparar búsqueda de documentación pendiente del ticket {case_id}.",
                )
            if "escalation" in intent_name:
                return PublicReplyDecision(
                    category="ticket_escalation",
                    text=(
                        f"Entiendo. En esta demo no puedo escalar realmente el ticket {case_id}, porque no estoy conectado al sistema operativo del cliente. "
                        "Lo que haría ACA es detectar la prioridad, ordenar el motivo del bloqueo y preparar la derivación con contexto para que la persona que lo tome no tenga que empezar de cero."
                    ),
                    next_step=f"Ordenar motivo de escalamiento del ticket {case_id}.",
                )
            return PublicReplyDecision(
                category="ticket_status",
                text=(
                    "Te cuento que en esta demo no tengo conexión real al sistema del cliente, así que no puedo ver el estado verdadero del caso. "
                    f"Lo que sí puedo hacer es mostrarte cómo interpretaría la consulta: detecto que querés consultar el ticket {case_id} y prepararía la búsqueda de estado actual, responsable y próximo paso 😊"
                ),
                next_step=f"Preparar consulta del ticket {case_id}: estado, responsable y próximo paso.",
            )

        if domain == "operations.basic":
            process_name = entities.get("process_name")
            subject = f"el proceso {process_name}" if process_name else "ese proceso"
            return PublicReplyDecision(
                category="operations",
                text=(
                    f"Puedo ayudarte a ordenar {subject}. En esta demo no tengo métricas reales conectadas, "
                    "pero sí puedo mostrar cómo ACA prepararía el análisis: señales, posibles trabas, responsable del tramo y próximo punto a revisar."
                ),
                next_step="Identificar señales, responsable y próximo punto de revisión.",
            )

        if intent_name == "demo.fallback":
            contextual = contextual_answer(state=state, frustrated=False)
            if contextual is not None:
                return contextual
            if state and state.fallback_count > 0:
                return PublicReplyDecision(
                    category="fallback_reformulated",
                    text=(
                        "Voy de nuevo, más simple: puedo ayudarte con tickets de demo, siniestros, documentación, plazos, franquicia, cristales o robo parcial. "
                        "Si querés probar algo concreto, escribí por ejemplo: ‘tuve un choque’ o ‘estado del ticket 12345’."
                    ),
                    next_step="Reformular opciones concretas sin repetir fallback.",
                )
            return PublicReplyDecision(
                category="fallback",
                text=(
                    "Con esta consulta todavía no tengo suficiente contexto para ayudarte bien. Puedo orientarte sobre siniestros, documentación, estados de trámite, "
                    "franquicia, cristales, robo parcial, plazos o tickets de demo. Contame qué querés resolver y avanzo desde ahí."
                ),
                next_step="Pedir objetivo concreto sin repetir fallback.",
            )

        return PublicReplyDecision(
            category="general",
            text=(
                "Puedo orientarte con eso dentro de los límites de la demo. No tengo acceso a sistemas reales, "
                "pero puedo ayudarte a ordenar la consulta, identificar qué información falta y preparar el próximo paso."
            ),
            next_step="Ordenar información disponible y próximo paso.",
        )


def capability_answer(*, state: PublicConversationState | None) -> PublicReplyDecision:
    suffix = ""
    if state and state.active_case_id:
        suffix = f" En el caso del ticket {state.active_case_id}, puedo mostrar qué buscaría: estado actual, área responsable y próximo paso."
    elif state and state.active_claim_type:
        suffix = f" Como veníamos hablando de {state.active_claim_type}, puedo ayudarte a ordenar documentación, canal de denuncia y próximos pasos."
    return PublicReplyDecision(
        category="capability",
        text=(
            "Puedo ayudarte de tres formas: orientar consultas de siniestros, explicar documentación o plazos, y mostrar cómo prepararía una gestión de ticket en esta demo. "
            "No consulto sistemas reales ni invento estados: cuando falta conexión o evidencia, lo aclaro y te digo qué dato haría falta."
            + suffix
        ),
        next_step="Elegir ticket, siniestro, documentación, plazo o cobertura.",
    )


def contextual_answer(*, state: PublicConversationState | None, frustrated: bool) -> PublicReplyDecision | None:
    if state is None:
        return None
    lead = "Sí, te entiendo. " if frustrated else ""
    if state.active_claim_type and (state.active_topic == "siniestro" or str(state.last_category or "").startswith("claim") or state.last_category in {"deductible", "upload_issue", "cleas"}):
        return PublicReplyDecision(
            category="claim_context_followup" if not frustrated else "claim_frustration_repair",
            text=(
                f"{lead}Sigo con el tema de {state.active_claim_type}. Puedo orientarte con documentación, canal de denuncia, plazos informativos y próximos pasos. "
                "Si hay lesionados, intervención policial compleja o el trámite está trabado legalmente, corresponde derivarlo con contexto a una persona."
            ),
            next_step=f"Continuar orientación sobre {state.active_claim_type}.",
        )
    if state.active_case_id:
        return PublicReplyDecision(
            category="ticket_context_followup" if not frustrated else "ticket_frustration_repair",
            text=(
                f"{lead}Sigo sobre el ticket {state.active_case_id}. En esta demo no puedo consultar el estado real, pero sí puedo mostrarte qué haría ACA: "
                "buscar estado actual, responsable, último movimiento y próximo paso. También puedo mostrar cómo prepararía una derivación con contexto si el caso estuviera trabado."
            ),
            next_step=f"Mantener contexto del ticket {state.active_case_id} y ofrecer seguimiento o derivación.",
        )
    if state.last_category in {"fallback", "clarification", "fallback_reformulated"}:
        return PublicReplyDecision(
            category="fallback_reformulated",
            text=(
                "Voy de nuevo, más simple: puedo ayudarte si la consulta entra en alguno de estos temas: ticket, siniestro, documentación, plazo, franquicia, cristales o robo parcial. "
                "Si querés probar la demo, escribí por ejemplo: ‘tuve un choque’ o ‘estado del ticket 12345’."
            ),
            next_step="Reformular opciones concretas.",
        )
    return None


def claim_answer(*, compact: str, state: PublicConversationState | None) -> PublicReplyDecision | None:
    if mentions_collision(compact):
        return PublicReplyDecision(
            category="claim_collision",
            text=(
                "Lamento lo del choque. Para orientarte bien, primero separaría dos cosas: si hubo lesionados y si querés denunciar tu propio siniestro o reclamar como tercero. "
                "En general, para un choque se suele necesitar denuncia administrativa, fotos de los daños y patente, cédula, registro y, según el caso, presupuesto de reparación. "
                "El próximo paso sería iniciar la denuncia por el canal digital correspondiente y cargar esa documentación."
            ),
            next_step="Confirmar si hubo lesionados y canal de póliza.",
        )
    if asks_documentation(compact) and state and state.active_claim_type == "choque":
        return PublicReplyDecision(
            category="claim_collision_documents",
            text=(
                "Para el choque, la documentación base suele ser: denuncia administrativa del siniestro, fotos de los daños y de la patente, cédula verde o azul, registro de conducir y, si corresponde, presupuesto de reparación. "
                "Si hubo terceros o lesionados, conviene tratarlo con más cuidado y derivar con contexto."
            ),
            next_step="Reunir documentación y confirmar si hubo lesionados o tercero involucrado.",
        )
    if mentions_glass(compact):
        return PublicReplyDecision(
            category="claim_glass",
            text=(
                "Para rotura de cristales, normalmente se piden fotos donde se vea claramente el daño y una foto de la patente. "
                "Según el caso, pueden derivarte a una cristalería de la red o pedir presupuesto si corresponde reintegro."
            ),
            next_step="Cargar fotos del daño y patente.",
        )
    if mentions_theft(compact):
        return PublicReplyDecision(
            category="claim_theft",
            text=(
                "Para un robo parcial, lo importante es hacer la denuncia policial y detallar qué elementos fueron robados. "
                "También suelen pedirse fotos de los daños, patente y presupuesto de reposición de los elementos afectados."
            ),
            next_step="Hacer denuncia policial y reunir fotos, patente y presupuesto.",
        )
    if "franquicia" in compact:
        return PublicReplyDecision(
            category="deductible",
            text=(
                "La franquicia es la parte del arreglo que queda a cargo del asegurado cuando la póliza lo establece. "
                "La aseguradora cubre el monto que supere esa franquicia. Si necesitás reclamarle esa parte a un tercero, suele corresponder carta de franquicia cuando el siniestro ya está cerrado y aprobado."
            ),
            next_step="Confirmar cobertura y si el siniestro está cerrado/aprobado.",
        )
    if any(phrase in compact for phrase in ["app no", "no puedo subir", "subir fotos", "subir documentacion", "subir documentacion"]):
        return PublicReplyDecision(
            category="upload_issue",
            text=(
                "Si la app no te deja subir fotos o documentación, probaría primero con archivos JPG o PNG, menor peso y, si sigue fallando, desde incógnito o una computadora. "
                "Si el error persiste, corresponde usar el canal de contingencia habilitado para enviar la documentación."
            ),
            next_step="Verificar formato/peso y probar canal alternativo si persiste.",
        )
    if "cleas" in compact:
        return PublicReplyDecision(
            category="cleas",
            text=(
                "CLEAS aplica en choques leves entre dos vehículos asegurados en compañías adheridas, sin lesionados y con responsable claro. "
                "La idea es que tu propia compañía gestione la reparación y luego compense con la aseguradora responsable. En la demo te puedo orientar, pero la aplicación real depende del análisis del caso."
            ),
            next_step="Confirmar compañías, ausencia de lesionados y responsabilidad del hecho.",
        )
    return None


def is_greeting(compact: str) -> bool:
    return compact in {"hola", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi"}


def is_identity_question(compact: str) -> bool:
    return any(phrase in compact for phrase in [
        "sos un bot", "eres un bot", "sos bot", "que sos", "quien sos", "que eres", "quien eres"
    ])


def is_ai_question(compact: str) -> bool:
    return any(phrase in compact for phrase in [
        "no tenes ia", "tenes ia", "tienes ia", "inteligencia artificial", "chatgpt", "ia externa"
    ])


def is_capability_question(compact: str) -> bool:
    return any(phrase in compact for phrase in [
        "que podes hacer", "que puedes hacer", "podes hacer algo", "puedes hacer algo", "que haces", "solo podes responder", "solo puedes responder", "podes responder", "puedes responder"
    ])


def is_confusion_question(compact: str) -> bool:
    return compact in {"eh", "ehh", "que", "como", "no entiendo", "no entendi"}


def is_short_ack(compact: str) -> bool:
    return compact in {"bueno", "bue", "bueh", "ok", "okay", "dale", "aja", "y"}


def is_frustration(compact: str) -> bool:
    return any(phrase in compact for phrase in [
        "bue", "no sirve", "inutil", "solo podes", "no entendes", "no entiende", "no tenes ia", "no hay ia", "es una demo rota"
    ])


def asks_documentation(compact: str) -> bool:
    return any(word in compact for word in ["documentacion", "papeles", "que necesito", "requisitos", "que tengo que presentar"])


def mentions_collision(compact: str) -> bool:
    return any(word in compact for word in ["choque", "colision", "me chocaron", "tuve un accidente", "siniestro auto"])


def mentions_glass(compact: str) -> bool:
    return any(word in compact for word in ["cristal", "vidrio", "parabrisas", "luneta"])


def mentions_theft(compact: str) -> bool:
    return any(word in compact for word in ["robo", "me robaron", "rueda", "bateria", "estereo"])


def normalize_public_text(value: str) -> str:
    return value.lower().strip()


def compact_text(value: str) -> str:
    text = normalize_public_text(value)
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    text = re.sub(r"([aeiou])\1+", r"\1", text)
    text = re.sub(r"([^aeiou])\1{2,}", r"\1", text)
    text = text.replace("¿", " ").replace("?", " ").replace("¡", " ").replace("!", " ")
    text = re.sub(r"[^a-z0-9ñáéíóúü\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
