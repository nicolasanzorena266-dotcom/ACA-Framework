from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from aca_core.text import normalize_search_text
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
        compact = compact_text(message)
        case_id = str(entities.get("case_id") or (state.active_case_id if state else "") or "") or None
        intent_name = str(intent.get("name") or "consulta")
        domain = str(pack.get("domain") or "")

        if is_greeting(compact):
            return PublicReplyDecision(
                category="greeting",
                text=(
                    "Hola ðŸ˜Š Soy ACA. Puedo orientarte sobre siniestros, documentaciÃ³n, plazos, franquicia, "
                    "cristales, robo parcial o mostrar cÃ³mo prepararÃ­a una consulta de ticket en esta demo. "
                    "No tengo conexiÃ³n real a sistemas del cliente, asÃ­ que no voy a inventar estados ni datos privados."
                ),
                next_step="Elegir un trÃ¡mite, siniestro o ticket de demo.",
            )

        if is_identity_question(compact):
            return PublicReplyDecision(
                category="identity",
                text=(
                    "Soy ACA, un asistente de atenciÃ³n en versiÃ³n demo ðŸ˜Š. Mi trabajo es entender quÃ© necesitÃ¡s, "
                    "mantener el contexto de la conversaciÃ³n y orientarte con la informaciÃ³n disponible. Si algo requiere "
                    "consultar un sistema real, te lo digo claro en vez de inventarlo."
                ),
                next_step="Continuar con la consulta activa o pedir capacidades.",
            )

        if is_ai_question(compact):
            return PublicReplyDecision(
                category="ai_limit",
                text=(
                    "Tengo una capa conversacional para esta demo, pero no estoy conectado a una IA externa libre ni a los sistemas reales del cliente. "
                    "La lÃ³gica de ACA es otra: primero entiende la consulta, sostiene el contexto, decide quÃ© puede hacer y despuÃ©s responde. "
                    "Lo que no puedo hacer es consultar un caso real o inventar datos. Si el dato no estÃ¡ disponible, te explico quÃ© buscarÃ­a o quÃ© paso conviene seguir."
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
                    "SÃ­, te entiendo: si repito una respuesta genÃ©rica, la demo no sirve. Puedo ayudarte mejor si lo llevamos a un caso concreto: "
                    "ticket, choque, cristales, robo parcial, franquicia, documentaciÃ³n, plazos o prÃ³ximos pasos."
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
                    "Me explico mejor: esta demo puede orientarte y mostrar cÃ³mo prepararÃ­a una gestiÃ³n, pero no consulta bases reales. "
                    "PodÃ©s probar con un ticket, un choque, cristales, robo parcial, franquicia, documentaciÃ³n o plazos."
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
                    "PasÃ¡melo y continÃºo con la orientaciÃ³n."
                ),
                next_step="Pedir el dato faltante y volver a evaluar.",
            )

        if domain == "customer.support" and case_id:
            if "documentation" in intent_name:
                return PublicReplyDecision(
                    category="ticket_documentation",
                    text=(
                        f"Te cuento que en esta demo no tengo conexiÃ³n real al sistema del cliente, asÃ­ que no puedo ver la documentaciÃ³n verdadera del ticket {case_id}. "
                        "Lo que sÃ­ puedo hacer es mostrarte cÃ³mo interpretarÃ­a la consulta: detecto que querÃ©s revisar documentaciÃ³n pendiente y prepararÃ­a la bÃºsqueda de archivos faltantes, responsable y prÃ³ximo paso ðŸ˜Š"
                    ),
                    next_step=f"Preparar bÃºsqueda de documentaciÃ³n pendiente del ticket {case_id}.",
                )
            if "escalation" in intent_name:
                return PublicReplyDecision(
                    category="ticket_escalation",
                    text=(
                        f"Entiendo. En esta demo no puedo escalar realmente el ticket {case_id}, porque no estoy conectado al sistema operativo del cliente. "
                        "Lo que harÃ­a ACA es detectar la prioridad, ordenar el motivo del bloqueo y preparar la derivaciÃ³n con contexto para que la persona que lo tome no tenga que empezar de cero."
                    ),
                    next_step=f"Ordenar motivo de escalamiento del ticket {case_id}.",
                )
            return PublicReplyDecision(
                category="ticket_status",
                text=(
                    "Te cuento que en esta demo no tengo conexiÃ³n real al sistema del cliente, asÃ­ que no puedo ver el estado verdadero del caso. "
                    f"Lo que sÃ­ puedo hacer es mostrarte cÃ³mo interpretarÃ­a la consulta: detecto que querÃ©s consultar el ticket {case_id} y prepararÃ­a la bÃºsqueda de estado actual, responsable y prÃ³ximo paso ðŸ˜Š"
                ),
                next_step=f"Preparar consulta del ticket {case_id}: estado, responsable y prÃ³ximo paso.",
            )

        if domain == "operations.basic":
            process_name = entities.get("process_name")
            subject = f"el proceso {process_name}" if process_name else "ese proceso"
            return PublicReplyDecision(
                category="operations",
                text=(
                    f"Puedo ayudarte a ordenar {subject}. En esta demo no tengo mÃ©tricas reales conectadas, "
                    "pero sÃ­ puedo mostrar cÃ³mo ACA prepararÃ­a el anÃ¡lisis: seÃ±ales, posibles trabas, responsable del tramo y prÃ³ximo punto a revisar."
                ),
                next_step="Identificar seÃ±ales, responsable y prÃ³ximo punto de revisiÃ³n.",
            )

        if intent_name == "demo.fallback":
            contextual = contextual_answer(state=state, frustrated=False)
            if contextual is not None:
                return contextual
            if state and state.fallback_count > 0:
                return PublicReplyDecision(
                    category="fallback_reformulated",
                    text=(
                        "Voy de nuevo, mÃ¡s simple: puedo ayudarte con tickets de demo, siniestros, documentaciÃ³n, plazos, franquicia, cristales o robo parcial. "
                        "Si querÃ©s probar algo concreto, escribÃ­ por ejemplo: â€˜tuve un choqueâ€™ o â€˜estado del ticket 12345â€™."
                    ),
                    next_step="Reformular opciones concretas sin repetir fallback.",
                )
            return PublicReplyDecision(
                category="fallback",
                text=(
                    "Con esta consulta todavÃ­a no tengo suficiente contexto para ayudarte bien. Puedo orientarte sobre siniestros, documentaciÃ³n, estados de trÃ¡mite, "
                    "franquicia, cristales, robo parcial, plazos o tickets de demo. Contame quÃ© querÃ©s resolver y avanzo desde ahÃ­."
                ),
                next_step="Pedir objetivo concreto sin repetir fallback.",
            )

        return PublicReplyDecision(
            category="general",
            text=(
                "Puedo orientarte con eso dentro de los lÃ­mites de la demo. No tengo acceso a sistemas reales, "
                "pero puedo ayudarte a ordenar la consulta, identificar quÃ© informaciÃ³n falta y preparar el prÃ³ximo paso."
            ),
            next_step="Ordenar informaciÃ³n disponible y prÃ³ximo paso.",
        )


def capability_answer(*, state: PublicConversationState | None) -> PublicReplyDecision:
    suffix = ""
    if state and state.active_case_id:
        suffix = f" En el caso del ticket {state.active_case_id}, puedo mostrar quÃ© buscarÃ­a: estado actual, Ã¡rea responsable y prÃ³ximo paso."
    elif state and state.active_claim_type:
        suffix = f" Como venÃ­amos hablando de {state.active_claim_type}, puedo ayudarte a ordenar documentaciÃ³n, canal de denuncia y prÃ³ximos pasos."
    return PublicReplyDecision(
        category="capability",
        text=(
            "Puedo ayudarte de tres formas: orientar consultas de siniestros, explicar documentaciÃ³n o plazos, y mostrar cÃ³mo prepararÃ­a una gestiÃ³n de ticket en esta demo. "
            "No consulto sistemas reales ni invento estados: cuando falta conexiÃ³n o evidencia, lo aclaro y te digo quÃ© dato harÃ­a falta."
            + suffix
        ),
        next_step="Elegir ticket, siniestro, documentaciÃ³n, plazo o cobertura.",
    )


def contextual_answer(*, state: PublicConversationState | None, frustrated: bool) -> PublicReplyDecision | None:
    if state is None:
        return None
    lead = "SÃ­, te entiendo. " if frustrated else ""
    if state.active_claim_type and (state.active_topic == "siniestro" or str(state.last_category or "").startswith("claim") or state.last_category in {"deductible", "upload_issue", "cleas"}):
        return PublicReplyDecision(
            category="claim_context_followup" if not frustrated else "claim_frustration_repair",
            text=(
                f"{lead}Sigo con el tema de {state.active_claim_type}. Puedo orientarte con documentaciÃ³n, canal de denuncia, plazos informativos y prÃ³ximos pasos. "
                "Si hay lesionados, intervenciÃ³n policial compleja o el trÃ¡mite estÃ¡ trabado legalmente, corresponde derivarlo con contexto a una persona."
            ),
            next_step=f"Continuar orientaciÃ³n sobre {state.active_claim_type}.",
        )
    if state.active_case_id:
        return PublicReplyDecision(
            category="ticket_context_followup" if not frustrated else "ticket_frustration_repair",
            text=(
                f"{lead}Sigo sobre el ticket {state.active_case_id}. En esta demo no puedo consultar el estado real, pero sÃ­ puedo mostrarte quÃ© harÃ­a ACA: "
                "buscar estado actual, responsable, Ãºltimo movimiento y prÃ³ximo paso. TambiÃ©n puedo mostrar cÃ³mo prepararÃ­a una derivaciÃ³n con contexto si el caso estuviera trabado."
            ),
            next_step=f"Mantener contexto del ticket {state.active_case_id} y ofrecer seguimiento o derivaciÃ³n.",
        )
    if state.last_category in {"fallback", "clarification", "fallback_reformulated"}:
        return PublicReplyDecision(
            category="fallback_reformulated",
            text=(
                "Voy de nuevo, mÃ¡s simple: puedo ayudarte si la consulta entra en alguno de estos temas: ticket, siniestro, documentaciÃ³n, plazo, franquicia, cristales o robo parcial. "
                "Si querÃ©s probar la demo, escribÃ­ por ejemplo: â€˜tuve un choqueâ€™ o â€˜estado del ticket 12345â€™."
            ),
            next_step="Reformular opciones concretas.",
        )
    return None


def claim_answer(*, compact: str, state: PublicConversationState | None) -> PublicReplyDecision | None:
    if mentions_collision(compact):
        return PublicReplyDecision(
            category="claim_collision",
            text=(
                "Lamento lo del choque. Para orientarte bien, primero separarÃ­a dos cosas: si hubo lesionados y si querÃ©s denunciar tu propio siniestro o reclamar como tercero. "
                "En general, para un choque se suele necesitar denuncia administrativa, fotos de los daÃ±os y patente, cÃ©dula, registro y, segÃºn el caso, presupuesto de reparaciÃ³n. "
                "El prÃ³ximo paso serÃ­a iniciar la denuncia por el canal digital correspondiente y cargar esa documentaciÃ³n."
            ),
            next_step="Confirmar si hubo lesionados y canal de pÃ³liza.",
        )
    if asks_documentation(compact) and state and state.active_claim_type == "choque":
        return PublicReplyDecision(
            category="claim_collision_documents",
            text=(
                "Para el choque, la documentaciÃ³n base suele ser: denuncia administrativa del siniestro, fotos de los daÃ±os y de la patente, cÃ©dula verde o azul, registro de conducir y, si corresponde, presupuesto de reparaciÃ³n. "
                "Si hubo terceros o lesionados, conviene tratarlo con mÃ¡s cuidado y derivar con contexto."
            ),
            next_step="Reunir documentaciÃ³n y confirmar si hubo lesionados o tercero involucrado.",
        )
    if mentions_glass(compact):
        return PublicReplyDecision(
            category="claim_glass",
            text=(
                "Para rotura de cristales, normalmente se piden fotos donde se vea claramente el daÃ±o y una foto de la patente. "
                "SegÃºn el caso, pueden derivarte a una cristalerÃ­a de la red o pedir presupuesto si corresponde reintegro."
            ),
            next_step="Cargar fotos del daÃ±o y patente.",
        )
    if mentions_theft(compact):
        return PublicReplyDecision(
            category="claim_theft",
            text=(
                "Para un robo parcial, lo importante es hacer la denuncia policial y detallar quÃ© elementos fueron robados. "
                "TambiÃ©n suelen pedirse fotos de los daÃ±os, patente y presupuesto de reposiciÃ³n de los elementos afectados."
            ),
            next_step="Hacer denuncia policial y reunir fotos, patente y presupuesto.",
        )
    if "franquicia" in compact:
        return PublicReplyDecision(
            category="deductible",
            text=(
                "La franquicia es la parte del arreglo que queda a cargo del asegurado cuando la pÃ³liza lo establece. "
                "La aseguradora cubre el monto que supere esa franquicia. Si necesitÃ¡s reclamarle esa parte a un tercero, suele corresponder carta de franquicia cuando el siniestro ya estÃ¡ cerrado y aprobado."
            ),
            next_step="Confirmar cobertura y si el siniestro estÃ¡ cerrado/aprobado.",
        )
    if any(phrase in compact for phrase in ["app no", "no puedo subir", "subir fotos", "subir documentacion", "subir documentacion"]):
        return PublicReplyDecision(
            category="upload_issue",
            text=(
                "Si la app no te deja subir fotos o documentaciÃ³n, probarÃ­a primero con archivos JPG o PNG, menor peso y, si sigue fallando, desde incÃ³gnito o una computadora. "
                "Si el error persiste, corresponde usar el canal de contingencia habilitado para enviar la documentaciÃ³n."
            ),
            next_step="Verificar formato/peso y probar canal alternativo si persiste.",
        )
    if "cleas" in compact:
        return PublicReplyDecision(
            category="cleas",
            text=(
                "CLEAS aplica en choques leves entre dos vehÃ­culos asegurados en compaÃ±Ã­as adheridas, sin lesionados y con responsable claro. "
                "La idea es que tu propia compaÃ±Ã­a gestione la reparaciÃ³n y luego compense con la aseguradora responsable. En la demo te puedo orientar, pero la aplicaciÃ³n real depende del anÃ¡lisis del caso."
            ),
            next_step="Confirmar compaÃ±Ã­as, ausencia de lesionados y responsabilidad del hecho.",
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


def compact_text(value: str) -> str:
    return normalize_search_text(value, typo_tolerant=True)
