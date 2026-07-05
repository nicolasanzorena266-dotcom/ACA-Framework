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
        normalized = _norm(message)
        readable = _readable_norm(message)
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
                    "Hola 😊 Soy ACA. Puedo orientarte sobre siniestros, documentación, estados de trámite, franquicia, plazos o tickets de demo. "
                    "No tengo conexión real a sistemas del cliente, así que no voy a inventar datos: si algo necesita consulta interna, te lo voy a aclarar."
                ),
                next_step="Elegir una consulta o contar qué trámite quiere resolver.",
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
                    "Soy ACA, un asistente de atención en versión demo. Mi trabajo es entender qué necesitás, mantener el contexto y orientarte sin inventar. "
                    "Cuando un dato requiere consultar un sistema real, te lo digo en vez de simular una respuesta."
                ),
                next_step="Explicar capacidades o continuar con la consulta activa.",
            )

        if _is_ai_question(readable):
            suffix = ""
            if state and state.active_case_id:
                suffix = f" Como veníamos con el ticket {state.active_case_id}, puedo seguir con ese contexto: mostrar cómo consultaría estado, responsable, último movimiento y próximo paso."
            elif state and state.active_claim_type:
                suffix = f" Como veníamos hablando de {state.active_claim_type}, puedo seguir con explicación simple, documentación, plazos o próximos pasos."
            return RepresentativeAnswer(
                category="ai_limit",
                text=(
                    "En esta demo no estoy conectado a una IA externa libre como ChatGPT ni a sistemas reales del cliente. "
                    + suffix
                    + " ACA funciona distinto: interpreta la consulta, conserva el contexto y responde con límites claros. "
                    "Lo que no puedo hacer es consultar un caso real, ver estados verdaderos o inventar datos privados. "
                    "Puedo ayudarte de tres formas: orientar consultas de siniestros como choque, cristales, robo parcial o franquicia; explicar documentación, plazos y próximos pasos; o simular cómo prepararía una consulta de ticket."
                ),
                next_step="Continuar con una consulta concreta o pedir una simulación de respuesta.",
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
                    "Me explico mejor: puedo orientarte sobre siniestros, documentación, plazos, franquicia, cristales, robo parcial o tickets de demo. "
                    "No consulto sistemas reales; muestro cómo debería pensar y responder un representante ideal con la información disponible."
                ),
                next_step="Ofrecer una consulta concreta o explicar capacidades.",
            )

        claim_answer = _claim_answer(readable, state=state)
        if claim_answer is not None:
            return claim_answer

        # Context-aware documentation questions must beat the generic required_entity
        # path, otherwise a follow-up like "qué documentación necesito" after
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
                        f"Para el ticket {case_id}, en una operación real revisaría qué documentación figura pendiente, quién debe aportarla y por qué canal cargarla. "
                        "En esta demo no puedo ver el expediente real, pero sí puedo mostrar el recorrido esperado: identificar faltantes, responsable actual y próximo paso para destrabar la gestión."
                    ),
                    next_step=f"Preparar búsqueda de documentación pendiente del ticket {case_id}.",
                )
            if "escalation" in intent_name:
                return RepresentativeAnswer(
                    category="ticket_escalation",
                    text=(
                        f"Para escalar el ticket {case_id}, primero ordenaría el motivo del bloqueo, la urgencia y el último movimiento. "
                        "En esta demo no puedo enviar la derivación real, pero sí prepararía un resumen para que una persona lo tome sin hacer repetir todo al cliente."
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
                    "pero sí puedo preparar el análisis: señales de demora, posible traba, responsable del tramo y próximo punto a revisar."
                ),
                next_step="Identificar señales, responsable y próximo punto de revisión.",
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
                    "Pasámelo y continúo con la orientación."
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
                    "Todavía no tengo un tema claro para resolver. Podés probar con algo concreto, por ejemplo: “tuve un choque”, “qué es la franquicia”, “se rompió el parabrisas” o “estado del ticket 12345”."
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
            suffix = f" Como veníamos con el ticket {state.active_case_id}, puedo mostrar cómo lo atendería: consultar estado, responsable, último movimiento y próximo paso."
        elif state and state.active_claim_type:
            suffix = f" Como veníamos hablando de {state.active_claim_type}, puedo seguir con explicación simple, documentación, plazos o próximos pasos."
        return RepresentativeAnswer(
            category="capability",
            text=(
                "Puedo ayudarte de tres formas: primero, orientar consultas de siniestros como choque, cristales, robo parcial o franquicia; segundo, explicar documentación, plazos y próximos pasos; tercero, simular cómo prepararía una consulta de ticket en esta demo. "
                "No invento estados ni datos privados: cuando haría falta conexión real, te lo marco claro."
                + suffix
            ),
            next_step="Elegir ticket, siniestro, documentación, plazo o cobertura.",
        )

    def _contextual_followup(self, *, state: PublicConversationState | None, case_id: Any | None = None) -> RepresentativeAnswer | None:
        if state is None:
            return None
        active_case = case_id or state.active_case_id
        if active_case:
            return RepresentativeAnswer(
                category="ticket_context_followup",
                text=(
                    f"Sigo sobre el ticket {active_case}. Como esta demo no consulta el sistema real, no puedo darte un estado verdadero; lo útil acá es mostrar cómo lo atendería un representante: pediría el estado actual, el área responsable, el último movimiento y el próximo paso. "
                    "Si querés, puedo mostrártelo como una respuesta modelo al cliente."
                ),
                next_step=f"Mantener contexto del ticket {active_case} y ofrecer respuesta modelo o derivación.",
            )
        if state.active_claim_type == "franquicia":
            return RepresentativeAnswer(
                category="deductible_context_followup",
                text=(
                    "Lo explico más simple: la franquicia es la parte del arreglo que paga el asegurado. Si el arreglo cuesta más que esa franquicia, la aseguradora cubre la diferencia según la póliza. "
                    "Si querés reclamar esa franquicia a un tercero, normalmente se habla de carta de franquicia y suele pedirse cuando el siniestro ya está cerrado y aprobado."
                ),
                next_step="Preguntar si quiere ejemplo, documentación o carta de franquicia.",
            )
        if state.active_claim_type:
            return RepresentativeAnswer(
                category="claim_context_followup",
                text=(
                    f"Sigo con el tema de {state.active_claim_type}. Puedo ayudarte con documentación, canal de denuncia, plazos informativos o próximos pasos. "
                    "Si hubo lesionados, intervención policial compleja o el trámite está trabado legalmente, ahí corresponde derivarlo con contexto a una persona."
                ),
                next_step=f"Continuar orientación sobre {state.active_claim_type}.",
            )
        if state.last_category in {"fallback", "clarification", "missing_information"}:
            return RepresentativeAnswer(
                category="fallback_reformulated",
                text=(
                    "Voy de nuevo, más simple: decime qué querés probar y lo llevo a un caso. Puede ser ticket, choque, cristales, robo parcial, franquicia, documentación o plazos. "
                    "Si querés ver una respuesta modelo, pedime “mostrame cómo le responderías a un cliente”."
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
                    "Para el choque, la documentación base suele ser: denuncia administrativa del siniestro, fotos de los daños y de la patente, cédula verde o azul, registro de conducir y, si corresponde, presupuesto de reparación. "
                    "Si hubo terceros o lesionados, conviene tratarlo con más cuidado y derivar con contexto."
                ),
                next_step="Reunir documentación y confirmar si hubo lesionados o tercero involucrado.",
            )
        if state.active_claim_type == "franquicia":
            return RepresentativeAnswer(
                category="deductible_documents",
                text=(
                    "Para una carta o reclamo de franquicia, primero tiene que estar claro que hubo un siniestro con cobertura de Todo Riesgo con Franquicia y que no fuiste responsable. En general se necesita el siniestro cerrado o aprobado, datos del tercero y respaldo del monto de franquicia que pagaste. "
                    "En una atención real revisaría la póliza, el estado del siniestro y si ya corresponde pedir la carta."
                ),
                next_step="Confirmar cobertura, responsabilidad y estado del siniestro.",
            )
        if state.active_claim_type == "cristales":
            return RepresentativeAnswer(
                category="claim_glass_documents",
                text="Para cristales, normalmente se piden fotos donde se vea claramente el daño y una foto de la patente. Según el caso, pueden derivarte a una cristalería de la red.",
                next_step="Cargar fotos del cristal y patente.",
            )
        if state.active_claim_type == "robo parcial":
            return RepresentativeAnswer(
                category="claim_theft_documents",
                text="Para robo parcial, normalmente se necesita denuncia policial, detalle de los elementos robados, fotos de los daños y presupuesto de reposición.",
                next_step="Reunir denuncia policial, fotos y presupuesto.",
            )
        return None

    def _frustration_answer(self, *, state: PublicConversationState | None, case_id: Any | None = None) -> RepresentativeAnswer:
        active_case = case_id or (state.active_case_id if state else None)
        if active_case:
            return RepresentativeAnswer(
                category="frustration_ticket",
                text=(
                    f"Tenés razón: repetir que no tengo conexión real no ayuda mucho. Para el ticket {active_case}, una respuesta de atención tendría que verse así: “Voy a revisar el estado del caso para confirmarte en qué instancia está, quién lo tiene asignado y cuál es el próximo paso. Si encuentro documentación pendiente o una derivación abierta, te lo voy a indicar con el canal correspondiente para que no tengas que volver a consultar por lo mismo”. "
                    "En esta demo no puedo consultar ese estado real, pero esa es la forma en la que ACA debería orientar al cliente."
                ),
                next_step="Ofrecer respuesta modelo al cliente para el ticket activo.",
            )
        if state and state.active_claim_type:
            return RepresentativeAnswer(
                category="frustration_claim",
                text=(
                    f"Tenés razón, me faltó bajar la respuesta al caso. Sigamos con {state.active_claim_type}: puedo explicarlo simple, decirte qué documentación suele pedirse o mostrar cómo se lo respondería a un cliente."
                ),
                next_step=f"Reformular sobre {state.active_claim_type}.",
            )
        return RepresentativeAnswer(
            category="frustration_general",
            text=(
                "Tenés razón: si respondo genérico, la demo no sirve. Dame un caso concreto —ticket, choque, franquicia, cristales o robo parcial— y te respondo como representante, con límite claro y próximo paso."
            ),
            next_step="Pedir caso concreto y responder como representante.",
        )

    def _client_example_answer(self, *, state: PublicConversationState | None, case_id: Any | None = None) -> RepresentativeAnswer | None:
        active_case = case_id or (state.active_case_id if state else None)
        if active_case:
            return RepresentativeAnswer(
                category="ticket_client_example",
                text=(
                    f"Claro. Si un cliente preguntara por el ticket {active_case}, ACA debería responder algo así: “Te cuento que voy a revisar el estado del caso para confirmarte en qué instancia está, quién lo tiene asignado y cuál es el próximo paso. Si detecto documentación pendiente o una derivación abierta, te lo voy a indicar con el canal correspondiente para que no tengas que volver a consultar por lo mismo”. "
                    "En esta demo no puedo hacer esa consulta real, pero ese sería el tipo de respuesta operativa esperada."
                ),
                next_step=f"Mostrar respuesta modelo para ticket {active_case}.",
            )
        if state and state.active_claim_type == "franquicia":
            return RepresentativeAnswer(
                category="deductible_client_example",
                text=(
                    "Claro. Si un cliente pregunta por franquicia, ACA debería responder así: “La franquicia es el monto que queda a tu cargo cuando tenés un siniestro cubierto por una póliza con franquicia. Si el arreglo supera ese importe, la aseguradora cubre la diferencia según las condiciones de la póliza. Si no fuiste responsable del choque, una vez aprobado el siniestro podemos orientarte para solicitar la carta de franquicia y reclamar ese monto al tercero”."
                ),
                next_step="Mostrar respuesta modelo sobre franquicia.",
            )
        if state and state.active_claim_type:
            return RepresentativeAnswer(
                category="claim_client_example",
                text=(
                    f"Claro. Para {state.active_claim_type}, ACA debería responder como representante: explicar qué documentación suele pedirse, qué canal usar, qué plazo puede informarse y cuándo corresponde derivar con contexto."
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
                "Lamento lo del choque. Para orientarte bien, primero separaría dos cosas: si hubo lesionados y si querés denunciar tu propio siniestro o reclamar como tercero. "
                "En general, para un choque se suele necesitar denuncia administrativa, fotos de los daños y patente, cédula, registro y, según el caso, presupuesto de reparación. "
                "El próximo paso sería iniciar la denuncia por el canal digital correspondiente y cargar esa documentación."
            ),
            next_step="Confirmar si hubo lesionados y canal de póliza.",
        )
    if any(word in readable for word in ["cristal", "vidrio", "parabrisas", "luneta"]):
        return RepresentativeAnswer(
            category="claim_glass",
            text=(
                "Para rotura de cristales, normalmente se piden fotos donde se vea claramente el daño y una foto de la patente. "
                "Según el caso, pueden derivarte a una cristalería de la red o pedir presupuesto si corresponde reintegro."
            ),
            next_step="Cargar fotos del daño y patente.",
        )
    if any(word in readable for word in ["robo", "robaron", "rueda", "bateria", "estereo"]):
        return RepresentativeAnswer(
            category="claim_theft",
            text=(
                "Para un robo parcial, lo importante es hacer la denuncia policial y detallar qué elementos fueron robados. "
                "También suelen pedirse fotos de los daños, patente y presupuesto de reposición de los elementos afectados."
            ),
            next_step="Hacer denuncia policial y reunir fotos, patente y presupuesto.",
        )
    if _mentions_deductible(readable):
        return RepresentativeAnswer(
            category="deductible",
            text=(
                "La franquicia es la parte del arreglo que queda a cargo del asegurado cuando la póliza lo establece. Dicho simple: si el arreglo cuesta más que la franquicia, la aseguradora cubre la diferencia según la póliza. "
                "Si no fuiste responsable del choque, después del análisis del siniestro suele corresponder pedir una carta de franquicia para reclamar ese importe al tercero."
            ),
            next_step="Confirmar cobertura, responsabilidad y si el siniestro está cerrado/aprobado.",
        )
    if any(phrase in readable for phrase in ["app no", "no puedo subir", "subir fotos", "subir documentacion"]):
        return RepresentativeAnswer(
            category="upload_issue",
            text=(
                "Si la app no te deja subir fotos o documentación, probaría primero con archivos JPG o PNG, menor peso y, si sigue fallando, desde incógnito o una computadora. "
                "Si el error persiste, corresponde usar el canal de contingencia habilitado para enviar la documentación."
            ),
            next_step="Verificar formato/peso y probar canal alternativo si persiste.",
        )
    return None


def _human_missing_entity(value: str) -> str:
    return {"case_id": "número de ticket o caso", "process_name": "nombre del proceso", "metric_name": "nombre de la métrica"}.get(value, value.replace("_", " "))


def _is_greeting(readable: str) -> bool:
    compact = readable.strip(" .!?¿¡")
    return compact in {"hola", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches", "hello", "hi"}


def _is_identity_question(readable: str) -> bool:
    compact = readable.replace("¿", "").replace("?", "")
    return any(phrase in compact for phrase in ["sos un bot", "eres un bot", "sos bot", "que sos", "quien sos", "que eres", "quien eres"])


def _is_ai_question(readable: str) -> bool:
    compact = readable.replace("¿", "").replace("?", "")
    compact = compact.replace("tenees", "tenes").replace("teneés", "tenes")
    return any(phrase in compact for phrase in ["no tenes ia", "no tienes ia", "tenes ia", "tienes ia", "tene ia", "hay ia", "inteligencia artificial", "chatgpt", "ia externa"])


def _is_capability_question(readable: str) -> bool:
    compact = readable.replace("¿", "").replace("?", "")
    compact = _loose_typos(compact)
    return any(phrase in compact for phrase in ["que podes hacer", "que puedes hacer", "podes hacer algo", "puedes hacer algo", "solo podes responder", "solo puedes responder", "podes responder", "puedes responder", "que haces", "podes hacer", "puedes hacer"])


def _is_confusion_question(readable: str) -> bool:
    compact = readable.strip().replace("¿", "").replace("?", "")
    return compact in {"eh", "ehh", "que", "como", "no entiendo", "no entendi"}


def _is_short_ack(readable: str) -> bool:
    compact = readable.strip(" .!?¿¡")
    return compact in {"bueno", "bue", "bueh", "ok", "okay", "dale", "aja"}


def _is_frustrated(readable: str) -> bool:
    return any(phrase in readable for phrase in ["no estas siendo", "no sos de ayuda", "no sirve", "inutil", "solo repetis", "me repetis", "otra vez lo mismo", "ya me dijiste", "me dijiste", "no ayuda"])


def _asks_for_client_example(readable: str) -> bool:
    return any(phrase in readable for phrase in ["mostrame", "como seria", "como le responderias", "respuesta a un cliente", "responderias a un cliente", "probar como", "ejemplo de respuesta"])


def _asks_documentation(readable: str) -> bool:
    return any(word in readable for word in ["documentacion", "papeles", "que necesito", "requisitos", "que debo presentar", "que tengo que presentar"])


def _mentions_deductible(readable: str) -> bool:
    return "franqui" in readable or "franquisia" in readable or "franquicia" in readable


def _loose_typos(value: str) -> str:
    # La demo pública recibe tipeo humano real: vocales alargadas, ansiedad de teclado
    # y frases con una letra de más. Normalizamos solo para detectar actos conversacionales;
    # nunca para fabricar datos.
    return re.sub(r"([aeiou])\1{1,}", r"\1", value)


def _readable_norm(value: str) -> str:
    return _strip_accents(value.lower()).strip()


def _strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")


def _norm(value: str) -> str:
    return value.lower().strip()
