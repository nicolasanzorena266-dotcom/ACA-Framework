from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping


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
    ) -> RepresentativeAnswer:
        normalized = _norm(message)
        case_id = entities.get("case_id")
        missing = entities.get("missing_required")

        if _is_identity_question(normalized):
            return RepresentativeAnswer(
                category="identity",
                text=(
                    "Soy ACA 😊. En esta demo actúo como un asistente de atención: intento entender qué necesitás, "
                    "orientarte con la información disponible y decirte con claridad cuando no tengo acceso real a un sistema. "
                    "No estoy conectado a los datos del cliente, así que no voy a inventar estados, pagos ni gestiones."
                ),
            )

        if _is_capability_question(normalized):
            return RepresentativeAnswer(
                category="capability",
                text=(
                    "Tengo una capa de interpretación y respuesta para esta demo, pero no estoy conectado a una IA externa libre ni a sistemas reales del cliente. "
                    "Por eso puedo orientarte, explicar próximos pasos y mostrar cómo prepararía una consulta; lo que no puedo hacer es consultar un caso real o inventar datos."
                ),
            )

        if _is_confusion_question(normalized):
            return RepresentativeAnswer(
                category="clarification",
                text=(
                    "Me explico mejor: cuando hablás de un ticket o trámite, esta demo no consulta una base real. "
                    "Lo que hace es interpretar qué necesitás y mostrar qué acción prepararía: por ejemplo buscar estado actual, responsable y próximo paso."
                ),
            )

        claim_answer = _claim_answer(normalized)
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
                )
            if "escalation" in intent_name:
                return RepresentativeAnswer(
                    category="ticket_escalation",
                    text=(
                        f"Entiendo. En esta demo no puedo escalar realmente el ticket {case_id}, porque no estoy conectado al sistema operativo del cliente. "
                        "Lo que haría ACA es detectar la prioridad, ordenar el motivo del bloqueo y preparar la derivación con contexto para que la persona que lo tome no tenga que empezar de cero."
                    ),
                )
            return RepresentativeAnswer(
                category="ticket_status",
                text=(
                    f"Te cuento que en esta demo no tengo conexión real al sistema del cliente, así que no puedo ver el estado verdadero del caso. "
                    f"Lo que sí puedo hacer es mostrarte cómo interpretaría la consulta: detecto que querés consultar el ticket {case_id} y prepararía la búsqueda de estado actual, responsable y próximo paso 😊"
                ),
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
            )

        if intent_name == "demo.fallback":
            return RepresentativeAnswer(
                category="fallback",
                text=(
                    "Te entiendo. Con lo que tengo cargado en esta demo todavía no puedo resolver esa consulta de forma confiable. "
                    "Puedo orientarte mejor si me pasás un número de ticket, el tipo de trámite o qué necesitás lograr puntualmente."
                ),
            )

        return RepresentativeAnswer(
            category="general",
            text=(
                "Puedo orientarte con eso dentro de los límites de la demo. No tengo acceso a sistemas reales, "
                "pero puedo ayudarte a ordenar la consulta, identificar qué información falta y preparar el próximo paso."
            ),
        )


def _claim_answer(normalized: str) -> RepresentativeAnswer | None:
    if any(word in normalized for word in ["choque", "choque", "colision", "colisión", "me chocaron", "tuve un accidente"]):
        return RepresentativeAnswer(
            category="claim_collision",
            text=(
                "Lamento lo del choque. Para orientarte bien, primero separaría dos cosas: si hubo lesionados y si querés denunciar tu propio siniestro o reclamar como tercero. "
                "En general, para un choque se suele necesitar la denuncia administrativa, fotos de los daños y patente, cédula, registro y, según el caso, presupuesto de reparación. "
                "El próximo paso sería iniciar la denuncia por el canal digital correspondiente y cargar esa documentación."
            ),
            next_step="Confirmar si hubo lesionados y canal de póliza.",
        )
    if any(word in normalized for word in ["cristal", "vidrio", "parabrisas", "luneta"]):
        return RepresentativeAnswer(
            category="claim_glass",
            text=(
                "Para rotura de cristales, normalmente se piden fotos donde se vea claramente el daño y una foto de la patente. "
                "Según el caso, pueden derivarte a una cristalería de la red o pedir presupuesto si corresponde reintegro."
            ),
        )
    if any(word in normalized for word in ["robo", "me robaron", "rueda", "bateria", "batería", "estereo", "estéreo"]):
        return RepresentativeAnswer(
            category="claim_theft",
            text=(
                "Para un robo parcial, lo importante es hacer la denuncia policial y detallar qué elementos fueron robados. "
                "También suelen pedirse fotos de los daños, patente y presupuesto de reposición de los elementos afectados."
            ),
        )
    if any(word in normalized for word in ["franquicia", "franquicia"]):
        return RepresentativeAnswer(
            category="deductible",
            text=(
                "La franquicia es la parte del arreglo que queda a cargo del asegurado cuando la póliza lo establece. "
                "La aseguradora cubre el monto que supere esa franquicia. Si necesitás reclamarle esa parte a un tercero, suele corresponder carta de franquicia cuando el siniestro ya está cerrado y aprobado."
            ),
        )
    return None


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


def _is_capability_question(normalized: str) -> bool:
    compact = normalized.replace("¿", "").replace("?", "")
    return any(phrase in compact for phrase in [
        "no tenes ia",
        "no tienes ia",
        "tenes ia",
        "tienes ia",
        "tenés ia",
        "solo podes responder",
        "solo podés responder",
        "solo puedes responder",
        "podes responder",
        "podés responder",
        "puedes responder",
        "inteligencia artificial",
        "chatgpt",
    ])


def _is_confusion_question(normalized: str) -> bool:
    compact = normalized.strip().replace("¿", "").replace("?", "")
    return compact in {"eh", "ehh", "que", "qué", "cómo", "como", "no entiendo", "no entendi", "no entendí"}


def _norm(value: str) -> str:
    return value.lower().strip()
