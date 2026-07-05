from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Mapping

from aca_os.public_conversation_state import PublicConversationState


@dataclass(frozen=True)
class RepresentativeAnswer:
    text: str
    category: str
    next_step: str | None = None


class RepresentativeAnswerComposer:
    """Compose public, representative-style answers from deterministic runtime output.

    The runtime may expose intent, flow and entities internally. This composer is
    the public language layer: it communicates limits, orientation and next step
    without leaking routing jargon into the chat.
    """

    def compose(
        self,
        *,
        message: str,
        pack: Mapping[str, Any],
        intent: Mapping[str, Any],
        flow: Mapping[str, Any],
        entities: Mapping[str, Any],
        state: PublicConversationState | None = None,
    ) -> RepresentativeAnswer:
        normalized = _norm(message)
        case_id = entities.get("case_id") or (state.active_case_id if state else None)
        missing = entities.get("missing_required")

        if _is_greeting(normalized):
            return RepresentativeAnswer(
                category="greeting",
                text=(
                    "Hola 😊 Soy ACA. Puedo orientarte sobre siniestros, documentación, estados de trámite, próximos pasos "
                    "o mostrar cómo prepararía una consulta de ticket en esta demo. No tengo conexión real a sistemas del cliente, "
                    "así que no voy a inventar estados ni datos privados."
                ),
                next_step="Elegir una consulta o contar qué trámite quiere resolver.",
            )

        if _is_identity_question(normalized):
            return RepresentativeAnswer(
                category="identity",
                text=(
                    "Soy ACA, un asistente de atención en versión demo 😊. Mi trabajo es entender qué necesitás, orientarte con la información disponible "
                    "y aclarar cuando algo requiere consultar un sistema real. En esta demo no puedo ver datos privados ni estados verdaderos de tickets."
                ),
                next_step="Explicar capacidades o continuar con la consulta activa.",
            )

        if _is_ai_question(normalized):
            return RepresentativeAnswer(
                category="ai_limit",
                text=(
                    "Tengo una capa de interpretación y respuesta para esta demo, pero no estoy conectado a una IA externa libre ni a sistemas reales del cliente. "
                    "La idea es que ACA no invente: primero entiende la consulta, después decide qué puede hacer y recién ahí responde. Lo que no puedo hacer es consultar un caso real o inventar datos. Si el dato requiere sistema real, te lo digo claro."
                ),
                next_step="Continuar con una consulta concreta o ver el proceso interno.",
            )

        if _is_capability_question(normalized):
            return self._capability_answer(state=state)

        if _is_confusion_question(normalized) or _is_short_ack(normalized):
            contextual = self._contextual_followup(state=state)
            if contextual is not None:
                return contextual
            return RepresentativeAnswer(
                category="clarification",
                text=(
                    "Me explico mejor: esta demo puede orientarte y mostrar cómo prepararía una gestión, pero no consulta bases reales. "
                    "Podés preguntarme por un ticket, documentación de un siniestro, plazos, franquicia, cristales, robo parcial o próximos pasos."
                ),
                next_step="Ofrecer una consulta concreta o explicar capacidades.",
            )

        claim_answer = _claim_answer(normalized, state=state)
        if claim_answer is not None:
            return claim_answer

        if isinstance(missing, list) and missing:
            readable = ", ".join(str(item).replace("_", " ") for item in missing)
            return RepresentativeAnswer(
                category="missing_information",
                text=(
                    f"Puedo ayudarte, pero para avanzar sin inventar me falta este dato: {readable}. "
                    "Pasámelo y continúo con la orientación."
                ),
                next_step="Pedir el dato faltante y volver a evaluar.",
            )

        intent_name = str(intent.get("name") or "consulta")
        domain = pack.get("domain")

        if domain == "customer.support" and case_id:
            if "documentation" in intent_name:
                return RepresentativeAnswer(
                    category="ticket_documentation",
                    text=(
                        f"Te cuento que en esta demo no tengo conexión real al sistema del cliente, así que no puedo ver la documentación verdadera del ticket {case_id}. "
                        "Lo que sí puedo hacer es mostrarte cómo interpretaría la consulta: detecto que querés revisar documentación pendiente y prepararía la búsqueda de archivos faltantes, responsable y próximo paso 😊"
                    ),
                    next_step=f"Preparar búsqueda de documentación pendiente del ticket {case_id}.",
                )
            if "escalation" in intent_name:
                return RepresentativeAnswer(
                    category="ticket_escalation",
                    text=(
                        f"Entiendo. En esta demo no puedo escalar realmente el ticket {case_id}, porque no estoy conectado al sistema operativo del cliente. "
                        "Lo que haría ACA es detectar la prioridad, ordenar el motivo del bloqueo y preparar la derivación con contexto para que la persona que lo tome no tenga que empezar de cero."
                    ),
                    next_step=f"Ordenar motivo de escalamiento del ticket {case_id}.",
                )
            return RepresentativeAnswer(
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
            return RepresentativeAnswer(
                category="operations",
                text=(
                    f"Puedo ayudarte a ordenar {subject}. En esta demo no tengo métricas reales conectadas, "
                    "pero sí puedo mostrar cómo ACA prepararía el análisis: identificaría señales, posibles trabas, responsable del tramo y próximo punto a revisar."
                ),
                next_step="Identificar señales, responsable y próximo punto de revisión.",
            )

        if intent_name == "demo.fallback":
            contextual = self._contextual_followup(state=state)
            if contextual is not None:
                return contextual
            return RepresentativeAnswer(
                category="fallback",
                text=(
                    "Con esta consulta todavía no tengo suficiente contexto para ayudarte bien. Puedo orientarte sobre siniestros, documentación, estados de trámite, "
                    "franquicia, cristales, robo parcial, plazos o tickets de demo. Contame qué querés resolver y avanzo desde ahí."
                ),
                next_step="Pedir objetivo concreto sin repetir fallback.",
            )

        return RepresentativeAnswer(
            category="general",
            text=(
                "Puedo orientarte con eso dentro de los límites de la demo. No tengo acceso a sistemas reales, "
                "pero puedo ayudarte a ordenar la consulta, identificar qué información falta y preparar el próximo paso."
            ),
            next_step="Ordenar información disponible y próximo paso.",
        )

    def _capability_answer(self, *, state: PublicConversationState | None) -> RepresentativeAnswer:
        suffix = ""
        if state and state.active_case_id:
            suffix = f" En el caso del ticket {state.active_case_id}, puedo mostrar qué buscaría: estado actual, área responsable y próximo paso."
        elif state and state.active_claim_type:
            suffix = f" Como veníamos hablando de {state.active_claim_type}, puedo ayudarte a ordenar documentación, canal de denuncia y próximos pasos."
        return RepresentativeAnswer(
            category="capability",
            text=(
                "Puedo ayudarte de tres formas: orientar consultas de siniestros, explicar documentación o plazos, y mostrar cómo prepararía una gestión de ticket en esta demo. "
                "No consulto sistemas reales ni invento estados: cuando falta conexión o evidencia, lo aclaro y te digo qué dato haría falta."
                + suffix
            ),
            next_step="Elegir ticket, siniestro, documentación, plazo o cobertura.",
        )

    def _contextual_followup(self, *, state: PublicConversationState | None) -> RepresentativeAnswer | None:
        if state is None:
            return None
        if state.active_case_id:
            return RepresentativeAnswer(
                category="ticket_context_followup",
                text=(
                    f"Sigo sobre el ticket {state.active_case_id}. En esta demo no puedo consultar el estado real, pero sí puedo mostrarte qué haría ACA: "
                    "buscar estado actual, responsable, último movimiento y próximo paso. Si querés, también puedo mostrar cómo prepararía una derivación con contexto."
                ),
                next_step=f"Mantener contexto del ticket {state.active_case_id} y ofrecer seguimiento o derivación.",
            )
        if state.active_claim_type:
            return RepresentativeAnswer(
                category="claim_context_followup",
                text=(
                    f"Sigo con el tema de {state.active_claim_type}. Puedo orientarte con documentación, canal de denuncia, plazos informativos y próximos pasos. "
                    "Si el caso tiene lesionados, intervención policial compleja o está trabado legalmente, ahí corresponde derivarlo con contexto a una persona."
                ),
                next_step=f"Continuar orientación sobre {state.active_claim_type}.",
            )
        if state.last_category in {"fallback", "clarification"}:
            return RepresentativeAnswer(
                category="fallback_reformulated",
                text=(
                    "Voy de nuevo, más simple: puedo ayudarte si la consulta entra en alguno de estos temas: ticket, siniestro, documentación, plazo, franquicia, cristales o robo parcial. "
                    "Si querés probar la demo, escribí por ejemplo: 'tuve un choque' o 'estado del ticket 12345'."
                ),
                next_step="Reformular opciones concretas.",
            )
        return None


def _claim_answer(normalized: str, *, state: PublicConversationState | None = None) -> RepresentativeAnswer | None:
    if any(word in normalized for word in ["choque", "colision", "colisión", "me chocaron", "tuve un accidente"]):
        return RepresentativeAnswer(
            category="claim_collision",
            text=(
                "Lamento lo del choque. Para orientarte bien, primero separaría dos cosas: si hubo lesionados y si querés denunciar tu propio siniestro o reclamar como tercero. "
                "En general, para un choque se suele necesitar denuncia administrativa, fotos de los daños y patente, cédula, registro y, según el caso, presupuesto de reparación. "
                "El próximo paso sería iniciar la denuncia por el canal digital correspondiente y cargar esa documentación."
            ),
            next_step="Confirmar si hubo lesionados y canal de póliza.",
        )
    if _asks_documentation(normalized) and state and state.active_claim_type == "choque":
        return RepresentativeAnswer(
            category="claim_collision_documents",
            text=(
                "Para el choque, la documentación base suele ser: denuncia administrativa del siniestro, fotos de los daños y de la patente, cédula verde o azul, registro de conducir y, si corresponde, presupuesto de reparación. "
                "Si hubo terceros o lesionados, conviene tratarlo con más cuidado y derivar con contexto."
            ),
            next_step="Reunir documentación y confirmar si hubo lesionados o tercero involucrado.",
        )
    if any(word in normalized for word in ["cristal", "vidrio", "parabrisas", "luneta"]):
        return RepresentativeAnswer(
            category="claim_glass",
            text=(
                "Para rotura de cristales, normalmente se piden fotos donde se vea claramente el daño y una foto de la patente. "
                "Según el caso, pueden derivarte a una cristalería de la red o pedir presupuesto si corresponde reintegro."
            ),
            next_step="Cargar fotos del daño y patente.",
        )
    if any(word in normalized for word in ["robo", "me robaron", "rueda", "bateria", "batería", "estereo", "estéreo"]):
        return RepresentativeAnswer(
            category="claim_theft",
            text=(
                "Para un robo parcial, lo importante es hacer la denuncia policial y detallar qué elementos fueron robados. "
                "También suelen pedirse fotos de los daños, patente y presupuesto de reposición de los elementos afectados."
            ),
            next_step="Hacer denuncia policial y reunir fotos, patente y presupuesto.",
        )
    if any(word in normalized for word in ["franquicia"]):
        return RepresentativeAnswer(
            category="deductible",
            text=(
                "La franquicia es la parte del arreglo que queda a cargo del asegurado cuando la póliza lo establece. "
                "La aseguradora cubre el monto que supere esa franquicia. Si necesitás reclamarle esa parte a un tercero, suele corresponder carta de franquicia cuando el siniestro ya está cerrado y aprobado."
            ),
            next_step="Confirmar cobertura y si el siniestro está cerrado/aprobado.",
        )
    if any(phrase in normalized for phrase in ["app no", "no puedo subir", "subir fotos", "subir documentacion", "subir documentación"]):
        return RepresentativeAnswer(
            category="upload_issue",
            text=(
                "Si la app no te deja subir fotos o documentación, probaría primero con archivos JPG o PNG, menor peso y, si sigue fallando, desde incógnito o una computadora. "
                "Si el error persiste, corresponde usar el canal de contingencia habilitado para enviar la documentación."
            ),
            next_step="Verificar formato/peso y probar canal alternativo si persiste.",
        )
    return None


def _is_greeting(normalized: str) -> bool:
    compact = _strip_accents(normalized).strip(" .!?¿¡")
    return compact in {"hola", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi"}


def _is_identity_question(normalized: str) -> bool:
    compact = normalized.replace("¿", "").replace("?", "")
    return any(phrase in compact for phrase in [
        "sos un bot",
        "eres un bot",
        "sos bot",
        "que sos",
        "quien sos",
        "qué sos",
        "quién sos",
        "que eres",
        "quien eres",
    ])


def _is_ai_question(normalized: str) -> bool:
    compact = normalized.replace("¿", "").replace("?", "")
    return any(phrase in compact for phrase in [
        "no tenes ia",
        "no tienes ia",
        "tenes ia",
        "tienes ia",
        "tenés ia",
        "inteligencia artificial",
        "chatgpt",
        "ia externa",
    ])


def _is_capability_question(normalized: str) -> bool:
    compact = normalized.replace("¿", "").replace("?", "")
    return any(phrase in compact for phrase in [
        "que podes hacer",
        "qué podés hacer",
        "que podés hacer",
        "que puedes hacer",
        "podes hacer algo",
        "podés hacer algo",
        "puedes hacer algo",
        "solo podes responder",
        "solo podés responder",
        "solo puedes responder",
        "podes responder",
        "podés responder",
        "puedes responder",
    ])


def _is_confusion_question(normalized: str) -> bool:
    compact = normalized.strip().replace("¿", "").replace("?", "")
    return compact in {"eh", "ehh", "que", "qué", "cómo", "como", "no entiendo", "no entendi", "no entendí"}


def _is_short_ack(normalized: str) -> bool:
    compact = normalized.strip(" .!?¿¡")
    return compact in {"bueno", "bue", "bueh", "ok", "okay", "dale", "aja", "ajá"}


def _asks_documentation(normalized: str) -> bool:
    return any(word in normalized for word in ["documentacion", "documentación", "papeles", "que necesito", "qué necesito", "requisitos"])


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def _norm(value: str) -> str:
    return value.lower().strip()
