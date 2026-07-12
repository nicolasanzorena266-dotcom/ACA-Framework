from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from aca_core.text import normalize_search_text, normalize_text
from aca_os.public_conversation_state import PublicConversationState


@dataclass(frozen=True)
class RepresentativeAnswer:
    text: str
    category: str
    next_step: str | None = None
    semantic_parse: Mapping[str, Any] | None = None
    policy_decision: Mapping[str, Any] | None = None
    planner_decision: Mapping[str, Any] | None = None
    supervisor_result: Mapping[str, Any] | None = None
    public_trace: Mapping[str, Any] | None = None
    developer_trace: Mapping[str, Any] | None = None


class RepresentativeAnswerComposer:
    """Public representative language layer for the deterministic runtime.

    The runtime can classify, route and expose entities. This composer decides how
    to speak to a person. It keeps internal terms out of the public chat and uses
    the active public conversation state before falling back.
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
        readable = normalize_text(message)
        case_id = entities.get("case_id") or (state.active_case_id if state else None)

        # Sprint 71 RC10: the public chat is now driven by a structured
        # conversational workflow. The legacy branches below remain as a
        # deterministic fallback, but the primary path separates semantic
        # understanding, policy, planning, generation, supervision and trace.
        try:
            from aca_os.public_conversation_workflow import PublicConversationWorkflow

            workflow = PublicConversationWorkflow().run(message=message, state=state, entities=entities)
            return RepresentativeAnswer(
                text=workflow.text,
                category=workflow.category,
                next_step=workflow.next_step,
                semantic_parse=workflow.semantic_parse,
                policy_decision=workflow.policy_decision,
                planner_decision=workflow.planner_decision,
                supervisor_result=workflow.supervisor_result,
                public_trace=workflow.public_trace,
                developer_trace=workflow.developer_trace,
            )
        except Exception:
            # Fallback must remain safe and non-magical; tests and the public demo
            # must keep running even if the optional workflow path fails.
            pass

        # Conversational acts come before domain-pack fallback/missing-entity logic.
        if _is_greeting(readable):
            return RepresentativeAnswer(
                category="greeting",
                text=(
                    "Hola ðŸ˜Š Soy ACA. Puedo orientarte sobre siniestros, documentaciÃ³n, estados de trÃ¡mite, franquicia, plazos o tickets de demo. "
                    "No tengo conexiÃ³n real a sistemas del cliente, asÃ­ que no voy a inventar datos: si algo necesita consulta interna, te lo voy a aclarar."
                ),
                next_step="Elegir una consulta o contar quÃ© trÃ¡mite quiere resolver.",
            )

        if _asks_for_client_example(readable):
            example = self._client_example_answer(state=state, case_id=case_id)
            if example is not None:
                return example

        if _is_frustrated(readable):
            return self._frustration_answer(state=state, case_id=case_id)

        if _is_identity_question(readable):
            return RepresentativeAnswer(
                category="identity",
                text=(
                    "Soy ACA, un asistente de atenciÃ³n en versiÃ³n demo. Mi trabajo es entender quÃ© necesitÃ¡s, mantener el contexto y orientarte sin inventar. "
                    "Cuando un dato requiere consultar un sistema real, te lo digo en vez de simular una respuesta."
                ),
                next_step="Explicar capacidades o continuar con la consulta activa.",
            )

        if _is_ai_question(readable):
            suffix = ""
            if state and state.active_case_id:
                suffix = f" Como venÃ­amos con el ticket {state.active_case_id}, puedo seguir con ese contexto: mostrar cÃ³mo consultarÃ­a estado, responsable, Ãºltimo movimiento y prÃ³ximo paso."
            elif state and state.active_claim_type:
                suffix = f" Como venÃ­amos hablando de {state.active_claim_type}, puedo seguir con explicaciÃ³n simple, documentaciÃ³n, plazos o prÃ³ximos pasos."
            return RepresentativeAnswer(
                category="ai_limit",
                text=(
                    "En esta demo no estoy conectado a una IA externa libre como ChatGPT ni a sistemas reales del cliente. "
                    + suffix
                    + " ACA funciona distinto: interpreta la consulta, conserva el contexto y responde con lÃ­mites claros. "
                    "Lo que no puedo hacer es consultar un caso real, ver estados verdaderos o inventar datos privados. "
                    "Puedo ayudarte de tres formas: orientar consultas de siniestros como choque, cristales, robo parcial o franquicia; explicar documentaciÃ³n, plazos y prÃ³ximos pasos; o simular cÃ³mo prepararÃ­a una consulta de ticket."
                ),
                next_step="Continuar con una consulta concreta o pedir una simulaciÃ³n de respuesta.",
            )

        if _is_capability_question(readable):
            return self._capability_answer(state=state)

        if _is_confusion_question(readable) or _is_short_ack(readable):
            contextual = self._contextual_followup(state=state, case_id=case_id)
            if contextual is not None:
                return contextual
            return RepresentativeAnswer(
                category="clarification",
                text=(
                    "Me explico mejor: puedo orientarte sobre siniestros, documentaciÃ³n, plazos, franquicia, cristales, robo parcial o tickets de demo. "
                    "No consulto sistemas reales; muestro cÃ³mo deberÃ­a pensar y responder un representante ideal con la informaciÃ³n disponible."
                ),
                next_step="Ofrecer una consulta concreta o explicar capacidades.",
            )

        claim_answer = _claim_answer(readable, state=state)
        if claim_answer is not None:
            return claim_answer

        # Context-aware documentation questions must beat the generic required_entity
        # path, otherwise a follow-up like "quÃ© documentaciÃ³n necesito" after
        # franquicia gets misread as ticket documentation and asks for case_id.
        contextual_docs = self._contextual_documentation_answer(readable, state=state)
        if contextual_docs is not None:
            return contextual_docs

        intent_name = str(intent.get("name") or "consulta")
        domain = pack.get("domain")

        if domain == "customer.support" and case_id:
            if "documentation" in intent_name:
                return RepresentativeAnswer(
                    category="ticket_documentation",
                    text=(
                        f"Para el ticket {case_id}, en una operaciÃ³n real revisarÃ­a quÃ© documentaciÃ³n figura pendiente, quiÃ©n debe aportarla y por quÃ© canal cargarla. "
                        "En esta demo no puedo ver el expediente real, pero sÃ­ puedo mostrar el recorrido esperado: identificar faltantes, responsable actual y prÃ³ximo paso para destrabar la gestiÃ³n."
                    ),
                    next_step=f"Preparar bÃºsqueda de documentaciÃ³n pendiente del ticket {case_id}.",
                )
            if "escalation" in intent_name:
                return RepresentativeAnswer(
                    category="ticket_escalation",
                    text=(
                        f"Para escalar el ticket {case_id}, primero ordenarÃ­a el motivo del bloqueo, la urgencia y el Ãºltimo movimiento. "
                        "En esta demo no puedo enviar la derivaciÃ³n real, pero sÃ­ prepararÃ­a un resumen para que una persona lo tome sin hacer repetir todo al cliente."
                    ),
                    next_step=f"Ordenar motivo de escalamiento del ticket {case_id}.",
                )
            return RepresentativeAnswer(
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
            return RepresentativeAnswer(
                category="operations",
                text=(
                    f"Puedo ayudarte a ordenar {subject}. En esta demo no tengo mÃ©tricas reales conectadas, "
                    "pero sÃ­ puedo preparar el anÃ¡lisis: seÃ±ales de demora, posible traba, responsable del tramo y prÃ³ximo punto a revisar."
                ),
                next_step="Identificar seÃ±ales, responsable y prÃ³ximo punto de revisiÃ³n.",
            )

        missing = entities.get("missing_required")
        if isinstance(missing, list) and missing:
            contextual = self._contextual_followup(state=state, case_id=case_id)
            if contextual is not None:
                return contextual
            readable_missing = ", ".join(_human_missing_entity(str(item)) for item in missing)
            return RepresentativeAnswer(
                category="missing_information",
                text=(
                    f"Puedo ayudarte, pero para avanzar sin inventar me falta este dato: {readable_missing}. "
                    "PasÃ¡melo y continÃºo con la orientaciÃ³n."
                ),
                next_step="Pedir el dato faltante y volver a evaluar.",
            )

        if intent_name == "demo.fallback":
            contextual = self._contextual_followup(state=state, case_id=case_id)
            if contextual is not None:
                return contextual
            return RepresentativeAnswer(
                category="fallback",
                text=(
                    "TodavÃ­a no tengo un tema claro para resolver. PodÃ©s probar con algo concreto, por ejemplo: â€œtuve un choqueâ€, â€œquÃ© es la franquiciaâ€, â€œse rompiÃ³ el parabrisasâ€ o â€œestado del ticket 12345â€."
                ),
                next_step="Pedir objetivo concreto sin repetir fallback.",
            )

        return RepresentativeAnswer(
            category="general",
            text=(
                "Puedo orientarte con eso dentro de los lÃ­mites de la demo. No tengo acceso a sistemas reales, "
                "pero puedo ayudarte a ordenar la consulta, identificar quÃ© informaciÃ³n falta y preparar el prÃ³ximo paso."
            ),
            next_step="Ordenar informaciÃ³n disponible y prÃ³ximo paso.",
        )

    def _capability_answer(self, *, state: PublicConversationState | None) -> RepresentativeAnswer:
        suffix = ""
        if state and state.active_case_id:
            suffix = f" Como venÃ­amos con el ticket {state.active_case_id}, puedo mostrar cÃ³mo lo atenderÃ­a: consultar estado, responsable, Ãºltimo movimiento y prÃ³ximo paso."
        elif state and state.active_claim_type:
            suffix = f" Como venÃ­amos hablando de {state.active_claim_type}, puedo seguir con explicaciÃ³n simple, documentaciÃ³n, plazos o prÃ³ximos pasos."
        return RepresentativeAnswer(
            category="capability",
            text=(
                "Puedo ayudarte de tres formas: primero, orientar consultas de siniestros como choque, cristales, robo parcial o franquicia; segundo, explicar documentaciÃ³n, plazos y prÃ³ximos pasos; tercero, simular cÃ³mo prepararÃ­a una consulta de ticket en esta demo. "
                "No invento estados ni datos privados: cuando harÃ­a falta conexiÃ³n real, te lo marco claro."
                + suffix
            ),
            next_step="Elegir ticket, siniestro, documentaciÃ³n, plazo o cobertura.",
        )

    def _contextual_followup(self, *, state: PublicConversationState | None, case_id: Any | None = None) -> RepresentativeAnswer | None:
        if state is None:
            return None
        active_case = case_id or state.active_case_id
        if active_case:
            return RepresentativeAnswer(
                category="ticket_context_followup",
                text=(
                    f"Sigo sobre el ticket {active_case}. Como esta demo no consulta el sistema real, no puedo darte un estado verdadero; lo Ãºtil acÃ¡ es mostrar cÃ³mo lo atenderÃ­a un representante: pedirÃ­a el estado actual, el Ã¡rea responsable, el Ãºltimo movimiento y el prÃ³ximo paso. "
                    "Si querÃ©s, puedo mostrÃ¡rtelo como una respuesta modelo al cliente."
                ),
                next_step=f"Mantener contexto del ticket {active_case} y ofrecer respuesta modelo o derivaciÃ³n.",
            )
        if state.active_claim_type == "franquicia":
            return RepresentativeAnswer(
                category="deductible_context_followup",
                text=(
                    "Lo explico mÃ¡s simple: la franquicia es la parte del arreglo que paga el asegurado. Si el arreglo cuesta mÃ¡s que esa franquicia, la aseguradora cubre la diferencia segÃºn la pÃ³liza. "
                    "Si querÃ©s reclamar esa franquicia a un tercero, normalmente se habla de carta de franquicia y suele pedirse cuando el siniestro ya estÃ¡ cerrado y aprobado."
                ),
                next_step="Preguntar si quiere ejemplo, documentaciÃ³n o carta de franquicia.",
            )
        if state.active_claim_type:
            return RepresentativeAnswer(
                category="claim_context_followup",
                text=(
                    f"Sigo con el tema de {state.active_claim_type}. Puedo ayudarte con documentaciÃ³n, canal de denuncia, plazos informativos o prÃ³ximos pasos. "
                    "Si hubo lesionados, intervenciÃ³n policial compleja o el trÃ¡mite estÃ¡ trabado legalmente, ahÃ­ corresponde derivarlo con contexto a una persona."
                ),
                next_step=f"Continuar orientaciÃ³n sobre {state.active_claim_type}.",
            )
        if state.last_category in {"fallback", "clarification", "missing_information"}:
            return RepresentativeAnswer(
                category="fallback_reformulated",
                text=(
                    "Voy de nuevo, mÃ¡s simple: decime quÃ© querÃ©s probar y lo llevo a un caso. Puede ser ticket, choque, cristales, robo parcial, franquicia, documentaciÃ³n o plazos. "
                    "Si querÃ©s ver una respuesta modelo, pedime â€œmostrame cÃ³mo le responderÃ­as a un clienteâ€."
                ),
                next_step="Reformular opciones concretas.",
            )
        return None

    def _contextual_documentation_answer(self, readable: str, *, state: PublicConversationState | None) -> RepresentativeAnswer | None:
        if not _asks_documentation(readable) or state is None:
            return None
        if state.active_claim_type == "choque":
            return RepresentativeAnswer(
                category="claim_collision_documents",
                text=(
                    "Para el choque, la documentaciÃ³n base suele ser: denuncia administrativa del siniestro, fotos de los daÃ±os y de la patente, cÃ©dula verde o azul, registro de conducir y, si corresponde, presupuesto de reparaciÃ³n. "
                    "Si hubo terceros o lesionados, conviene tratarlo con mÃ¡s cuidado y derivar con contexto."
                ),
                next_step="Reunir documentaciÃ³n y confirmar si hubo lesionados o tercero involucrado.",
            )
        if state.active_claim_type == "franquicia":
            return RepresentativeAnswer(
                category="deductible_documents",
                text=(
                    "Para una carta o reclamo de franquicia, primero tiene que estar claro que hubo un siniestro con cobertura de Todo Riesgo con Franquicia y que no fuiste responsable. En general se necesita el siniestro cerrado o aprobado, datos del tercero y respaldo del monto de franquicia que pagaste. "
                    "En una atenciÃ³n real revisarÃ­a la pÃ³liza, el estado del siniestro y si ya corresponde pedir la carta."
                ),
                next_step="Confirmar cobertura, responsabilidad y estado del siniestro.",
            )
        if state.active_claim_type == "cristales":
            return RepresentativeAnswer(
                category="claim_glass_documents",
                text="Para cristales, normalmente se piden fotos donde se vea claramente el daÃ±o y una foto de la patente. SegÃºn el caso, pueden derivarte a una cristalerÃ­a de la red.",
                next_step="Cargar fotos del cristal y patente.",
            )
        if state.active_claim_type == "robo parcial":
            return RepresentativeAnswer(
                category="claim_theft_documents",
                text="Para robo parcial, normalmente se necesita denuncia policial, detalle de los elementos robados, fotos de los daÃ±os y presupuesto de reposiciÃ³n.",
                next_step="Reunir denuncia policial, fotos y presupuesto.",
            )
        return None

    def _frustration_answer(self, *, state: PublicConversationState | None, case_id: Any | None = None) -> RepresentativeAnswer:
        active_case = case_id or (state.active_case_id if state else None)
        if active_case:
            return RepresentativeAnswer(
                category="frustration_ticket",
                text=(
                    f"TenÃ©s razÃ³n: repetir que no tengo conexiÃ³n real no ayuda mucho. Para el ticket {active_case}, una respuesta de atenciÃ³n tendrÃ­a que verse asÃ­: â€œVoy a revisar el estado del caso para confirmarte en quÃ© instancia estÃ¡, quiÃ©n lo tiene asignado y cuÃ¡l es el prÃ³ximo paso. Si encuentro documentaciÃ³n pendiente o una derivaciÃ³n abierta, te lo voy a indicar con el canal correspondiente para que no tengas que volver a consultar por lo mismoâ€. "
                    "En esta demo no puedo consultar ese estado real, pero esa es la forma en la que ACA deberÃ­a orientar al cliente."
                ),
                next_step="Ofrecer respuesta modelo al cliente para el ticket activo.",
            )
        if state and state.active_claim_type:
            return RepresentativeAnswer(
                category="frustration_claim",
                text=(
                    f"TenÃ©s razÃ³n, me faltÃ³ bajar la respuesta al caso. Sigamos con {state.active_claim_type}: puedo explicarlo simple, decirte quÃ© documentaciÃ³n suele pedirse o mostrar cÃ³mo se lo responderÃ­a a un cliente."
                ),
                next_step=f"Reformular sobre {state.active_claim_type}.",
            )
        return RepresentativeAnswer(
            category="frustration_general",
            text=(
                "TenÃ©s razÃ³n: si respondo genÃ©rico, la demo no sirve. Dame un caso concreto â€”ticket, choque, franquicia, cristales o robo parcialâ€” y te respondo como representante, con lÃ­mite claro y prÃ³ximo paso."
            ),
            next_step="Pedir caso concreto y responder como representante.",
        )

    def _client_example_answer(self, *, state: PublicConversationState | None, case_id: Any | None = None) -> RepresentativeAnswer | None:
        active_case = case_id or (state.active_case_id if state else None)
        if active_case:
            return RepresentativeAnswer(
                category="ticket_client_example",
                text=(
                    f"Claro. Si un cliente preguntara por el ticket {active_case}, ACA deberÃ­a responder algo asÃ­: â€œTe cuento que voy a revisar el estado del caso para confirmarte en quÃ© instancia estÃ¡, quiÃ©n lo tiene asignado y cuÃ¡l es el prÃ³ximo paso. Si detecto documentaciÃ³n pendiente o una derivaciÃ³n abierta, te lo voy a indicar con el canal correspondiente para que no tengas que volver a consultar por lo mismoâ€. "
                    "En esta demo no puedo hacer esa consulta real, pero ese serÃ­a el tipo de respuesta operativa esperada."
                ),
                next_step=f"Mostrar respuesta modelo para ticket {active_case}.",
            )
        if state and state.active_claim_type == "franquicia":
            return RepresentativeAnswer(
                category="deductible_client_example",
                text=(
                    "Claro. Si un cliente pregunta por franquicia, ACA deberÃ­a responder asÃ­: â€œLa franquicia es el monto que queda a tu cargo cuando tenÃ©s un siniestro cubierto por una pÃ³liza con franquicia. Si el arreglo supera ese importe, la aseguradora cubre la diferencia segÃºn las condiciones de la pÃ³liza. Si no fuiste responsable del choque, una vez aprobado el siniestro podemos orientarte para solicitar la carta de franquicia y reclamar ese monto al terceroâ€."
                ),
                next_step="Mostrar respuesta modelo sobre franquicia.",
            )
        if state and state.active_claim_type:
            return RepresentativeAnswer(
                category="claim_client_example",
                text=(
                    f"Claro. Para {state.active_claim_type}, ACA deberÃ­a responder como representante: explicar quÃ© documentaciÃ³n suele pedirse, quÃ© canal usar, quÃ© plazo puede informarse y cuÃ¡ndo corresponde derivar con contexto."
                ),
                next_step=f"Mostrar respuesta modelo sobre {state.active_claim_type}.",
            )
        return None


def _claim_answer(readable: str, *, state: PublicConversationState | None = None) -> RepresentativeAnswer | None:
    if _asks_documentation(readable) and state and state.active_claim_type:
        return None
    if any(word in readable for word in ["choque", "colision", "me chocaron", "accidente"]):
        return RepresentativeAnswer(
            category="claim_collision",
            text=(
                "Lamento lo del choque. Para orientarte bien, primero separarÃ­a dos cosas: si hubo lesionados y si querÃ©s denunciar tu propio siniestro o reclamar como tercero. "
                "En general, para un choque se suele necesitar denuncia administrativa, fotos de los daÃ±os y patente, cÃ©dula, registro y, segÃºn el caso, presupuesto de reparaciÃ³n. "
                "El prÃ³ximo paso serÃ­a iniciar la denuncia por el canal digital correspondiente y cargar esa documentaciÃ³n."
            ),
            next_step="Confirmar si hubo lesionados y canal de pÃ³liza.",
        )
    if any(word in readable for word in ["cristal", "vidrio", "parabrisas", "luneta"]):
        return RepresentativeAnswer(
            category="claim_glass",
            text=(
                "Para rotura de cristales, normalmente se piden fotos donde se vea claramente el daÃ±o y una foto de la patente. "
                "SegÃºn el caso, pueden derivarte a una cristalerÃ­a de la red o pedir presupuesto si corresponde reintegro."
            ),
            next_step="Cargar fotos del daÃ±o y patente.",
        )
    if any(word in readable for word in ["robo", "robaron", "rueda", "bateria", "estereo"]):
        return RepresentativeAnswer(
            category="claim_theft",
            text=(
                "Para un robo parcial, lo importante es hacer la denuncia policial y detallar quÃ© elementos fueron robados. "
                "TambiÃ©n suelen pedirse fotos de los daÃ±os, patente y presupuesto de reposiciÃ³n de los elementos afectados."
            ),
            next_step="Hacer denuncia policial y reunir fotos, patente y presupuesto.",
        )
    if _mentions_deductible(readable):
        return RepresentativeAnswer(
            category="deductible",
            text=(
                "La franquicia es la parte del arreglo que queda a cargo del asegurado cuando la pÃ³liza lo establece. Dicho simple: si el arreglo cuesta mÃ¡s que la franquicia, la aseguradora cubre la diferencia segÃºn la pÃ³liza. "
                "Si no fuiste responsable del choque, despuÃ©s del anÃ¡lisis del siniestro suele corresponder pedir una carta de franquicia para reclamar ese importe al tercero."
            ),
            next_step="Confirmar cobertura, responsabilidad y si el siniestro estÃ¡ cerrado/aprobado.",
        )
    if any(phrase in readable for phrase in ["app no", "no puedo subir", "subir fotos", "subir documentacion"]):
        return RepresentativeAnswer(
            category="upload_issue",
            text=(
                "Si la app no te deja subir fotos o documentaciÃ³n, probarÃ­a primero con archivos JPG o PNG, menor peso y, si sigue fallando, desde incÃ³gnito o una computadora. "
                "Si el error persiste, corresponde usar el canal de contingencia habilitado para enviar la documentaciÃ³n."
            ),
            next_step="Verificar formato/peso y probar canal alternativo si persiste.",
        )
    return None


def _human_missing_entity(value: str) -> str:
    return {"case_id": "nÃºmero de ticket o caso", "process_name": "nombre del proceso", "metric_name": "nombre de la mÃ©trica"}.get(value, value.replace("_", " "))


def _is_greeting(readable: str) -> bool:
    compact = readable.strip(" .!?Â¿Â¡")
    return compact in {"hola", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi"}


def _is_identity_question(readable: str) -> bool:
    compact = normalize_search_text(readable)
    return any(phrase in compact for phrase in ["sos un bot", "eres un bot", "sos bot", "que sos", "quien sos", "que eres", "quien eres"])


def _is_ai_question(readable: str) -> bool:
    compact = normalize_search_text(readable, typo_tolerant=True)
    return any(phrase in compact for phrase in ["no tenes ia", "no tienes ia", "tenes ia", "tienes ia", "tene ia", "hay ia", "inteligencia artificial", "chatgpt", "ia externa"])


def _is_capability_question(readable: str) -> bool:
    compact = normalize_search_text(readable, typo_tolerant=True)
    return any(phrase in compact for phrase in ["que podes hacer", "que puedes hacer", "podes hacer algo", "puedes hacer algo", "solo podes responder", "solo puedes responder", "podes responder", "puedes responder", "que haces", "podes hacer", "puedes hacer"])


def _is_confusion_question(readable: str) -> bool:
    compact = normalize_search_text(readable)
    return compact in {"eh", "ehh", "que", "como", "no entiendo", "no entendi"}


def _is_short_ack(readable: str) -> bool:
    compact = readable.strip(" .!?Â¿Â¡")
    return compact in {"bueno", "bue", "bueh", "ok", "okay", "dale", "aja"}


def _is_frustrated(readable: str) -> bool:
    return any(phrase in readable for phrase in ["no estas siendo", "no sos de ayuda", "no sirve", "inutil", "solo repetis", "me repetis", "otra vez lo mismo", "ya me dijiste", "me dijiste", "no ayuda"])


def _asks_for_client_example(readable: str) -> bool:
    return any(phrase in readable for phrase in ["mostrame", "como seria", "como le responderias", "respuesta a un cliente", "responderias a un cliente", "probar como", "ejemplo de respuesta"])


def _asks_documentation(readable: str) -> bool:
    return any(word in readable for word in ["documentacion", "papeles", "que necesito", "requisitos", "que debo presentar", "que tengo que presentar"])


def _mentions_deductible(readable: str) -> bool:
    return "franqui" in readable or "franquisia" in readable or "franquicia" in readable


