from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from aca_os.public_conversation_contracts import (
    InteractionSignals,
    PlannerDecision,
    PolicyDecision,
    SemanticParse,
    SupervisorResult,
    TraceBundle,
    contains_any,
    make_trace_id,
    normalize_text,
    now_ms,
)
from aca_os.public_conversation_state import PublicConversationState


@dataclass(frozen=True)
class ConversationWorkflowResult:
    text: str
    category: str
    next_step: str | None
    semantic_parse: Mapping[str, Any]
    policy_decision: Mapping[str, Any]
    planner_decision: Mapping[str, Any]
    supervisor_result: Mapping[str, Any]
    public_trace: Mapping[str, Any]
    developer_trace: Mapping[str, Any]


class SemanticUnderstandingLayer:
    """Coarse semantic layer for the public conversation runtime.

    This is deliberately not a giant intent enum. It creates a compact semantic
    contract that can later be filled by an LLM with structured outputs. The
    current implementation is an offline fallback so the public demo remains
    deterministic and testable.
    """

    def parse(self, *, message: str, state: PublicConversationState | None, entities: Mapping[str, Any] | None = None) -> SemanticParse:
        text = normalize_text(message)
        entities = dict(entities or {})
        known: list[str] = []
        missing: list[str] = []
        requires_tool = False
        topic: str | None = None
        intent = "general_guidance"
        goal = "orientarse"
        requested_action = "answer_with_guidance"
        risk = "low"
        confidence = 0.62
        refers_to_previous = _short_or_contextual(text)

        signals = InteractionSignals(
            frustration=_frustration_level(text),
            confusion=_level(text, ["no entiendo", "eh", "como seria", "que significa"], medium=False),
            urgency=_level(text, ["urgente", "ya", "hoy", "necesito", "sigo esperando", "sin novedades"], medium=False),
            repetition=contains_any(text, ["ya me dijiste", "otra vez", "mil veces", "repetis", "repetiste"]),
        )

        if _is_greeting(text):
            return SemanticParse(intent="saludo", topic="inicio", user_goal="iniciar_conversacion", signals=signals, confidence=0.95, requested_action="answer_with_capabilities")

        if signals.frustration in {"medium", "high"} or signals.repetition:
            return SemanticParse(intent="expresar_frustracion", topic=state.active_topic if state else None, user_goal="recibir_ayuda_sin_repeticion", known_facts=_state_facts(state), signals=signals, confidence=0.86, requested_action="repair", refers_to_previous=bool(state and (state.active_topic or state.active_case_id)))

        if contains_any(text, ["que podes hacer", "que puedes hacer", "podes hacer algo", "que haces", "capacidades", "ayuda"]):
            return SemanticParse(intent="consultar_capacidades", topic=state.active_topic if state else "capacidades", user_goal="saber_que_puede_hacer_aca", signals=signals, confidence=0.9, requested_action="answer_capabilities", refers_to_previous=bool(state and (state.active_topic or state.active_case_id)))

        if contains_any(text, ["sos un bot", "que sos", "quien sos", "tenes ia", "no tenes ia", "inteligencia artificial", "chatgpt", "solo podes responder"]):
            return SemanticParse(intent="consultar_identidad_o_ia", topic=state.active_topic if state else "identidad", user_goal="entender_limites_del_asistente", signals=signals, confidence=0.91, requested_action="answer_identity_or_ai_limits", refers_to_previous=bool(state and (state.active_topic or state.active_case_id)))

        if contains_any(text, ["derivame", "quiero hablar con una persona", "representante", "humano", "supervisor", "atienda alguien"]):
            return SemanticParse(intent="solicitar_derivacion", topic=state.active_topic if state else "derivacion", user_goal="hablar_con_una_persona", known_facts=_state_facts(state), signals=signals, confidence=0.92, requested_action="prepare_handoff", risk_level="medium", refers_to_previous=True)

        explicit_case_id = _extract_case_id(text)
        carried_case_id = entities.get("case_id") if state and getattr(state, "active_case_id", None) == entities.get("case_id") else None
        case_id = explicit_case_id or entities.get("case_id")
        if explicit_case_id:
            requires_tool = True
            topic = "ticket"
            intent = "consultar_estado_o_plazo"
            goal = "saber_estado_y_proximo_paso"
            known.append(f"ticket:{case_id}")
            requested_action = "consultar_estado_real"
            confidence = 0.88
            entities["case_id"] = str(case_id)
        elif carried_case_id and _short_or_contextual(text):
            topic = "ticket"
            intent = "general_guidance"
            goal = "continuar_contexto_ticket"
            known.append(f"ticket:{carried_case_id}")
            confidence = 0.78
            entities["case_id"] = str(carried_case_id)
        elif case_id:
            requires_tool = True
            topic = "ticket"
            intent = "consultar_estado_o_plazo"
            goal = "saber_estado_y_proximo_paso"
            known.append(f"ticket:{case_id}")
            requested_action = "consultar_estado_real"
            confidence = 0.88
            entities["case_id"] = str(case_id)

        claim_type = _detect_claim_type(text) or (state.active_claim_type if state and refers_to_previous else None)
        if claim_type:
            topic = "siniestro"
            entities["claim_type"] = claim_type
            known.append(f"tipo_siniestro:{claim_type}")
            confidence = max(confidence, 0.78)
            if contains_any(text, ["cargue", "cargué", "denuncia", "app", "ya lo hice", "ya la envie", "ya envie", "documentacion enviada", "envie la documentacion"]):
                known.append("denuncia_o_documentacion_cargada")
            if contains_any(text, ["sin novedades", "sigo esperando", "estado", "cuando", "cuanto tarda", "plazo", "plazos", "demora"]):
                intent = "consultar_estado_o_plazo"
                goal = "saber_cuando_tendra_respuesta"
                requires_tool = True
                requested_action = "answer_with_guidance"
            elif contains_any(text, ["documentacion", "documentación", "papeles", "que necesito", "requisitos"]):
                intent = "consultar_documentacion"
                goal = "saber_que_documentacion_corresponde"
            elif contains_any(text, ["canal", "denuncia", "donde", "app", "home banking"]):
                intent = "consultar_canal"
                goal = "saber_canal_de_denuncia"
            elif claim_type == "franquicia":
                intent = "consultar_concepto_o_reclamo"
                goal = "entender_franquicia"
            else:
                intent = "orientar_siniestro"
                goal = "entender_proximo_paso"

        if not claim_type and contains_any(text, ["denuncia", "app", "sin novedades", "sigo esperando"]):
            topic = "siniestro"
            intent = "consultar_estado_o_plazo"
            goal = "saber_si_hay_novedades"
            known.append("denuncia_cargada")
            missing.append("tipo_siniestro")
            requires_tool = True
            requested_action = "ask_clarification_or_orient"
            confidence = 0.76

        if contains_any(text, ["plazo", "plazos", "cuanto tarda", "cuando responden", "demora"]):
            intent = "consultar_estado_o_plazo"
            goal = "saber_cuando_tendra_respuesta"
            topic = topic or (state.active_topic if state else "siniestro")
            confidence = max(confidence, 0.84 if state and state.active_topic else 0.72)
            refers_to_previous = bool(state and state.active_topic)

        if contains_any(text, ["documentacion", "documentación", "papeles", "requisitos"]):
            intent = "consultar_documentacion"
            goal = "saber_que_documentacion_corresponde"
            topic = topic or (state.active_topic if state else "siniestro")
            confidence = max(confidence, 0.84 if state and state.active_claim_type else 0.7)
            refers_to_previous = bool(state and state.active_topic)

        if contains_any(text, ["canal de denuncia", "canal", "donde denuncio", "por donde"]):
            intent = "consultar_canal"
            goal = "saber_canal_de_denuncia"
            topic = topic or (state.active_topic if state else "siniestro")
            confidence = max(confidence, 0.8)
            refers_to_previous = bool(state and state.active_topic)

        if contains_any(text, ["ya lo hice", "ya la envie", "ya envie", "ya mande", "ya lo mande"]):
            intent = "informar_paso_realizado"
            goal = "evitar_repetir_pasos_y_saber_siguiente_paso"
            known.append("paso_previo_realizado")
            topic = state.active_topic if state else topic
            refers_to_previous = True
            confidence = 0.83

        if contains_any(text, ["mostrame", "como le responderias", "respuesta modelo", "ejemplo", "probar como"]):
            intent = "pedir_respuesta_modelo"
            goal = "ver_como_responderia_a_un_cliente"
            topic = state.active_topic if state else topic
            requested_action = "show_example"
            refers_to_previous = True
            confidence = 0.86

        return SemanticParse(
            intent=intent,
            topic=topic,
            user_goal=goal,
            known_facts=tuple(dict.fromkeys([*_state_facts(state), *known])),
            missing_facts=tuple(dict.fromkeys(missing)),
            signals=signals,
            confidence=confidence,
            requires_tool=requires_tool,
            risk_level=risk,  # type: ignore[arg-type]
            requested_action=requested_action,
            entities=entities,
            refers_to_previous=refers_to_previous,
        )


class ContextMergeEngine:
    def merge(self, *, state: PublicConversationState | None, parse: SemanticParse) -> dict[str, Any]:
        facts = set(getattr(state, "known_facts", ()) or ())
        facts.update(parse.known_facts)
        active_topic = parse.topic or (state.active_topic if state else None)
        claim_type = parse.entities.get("claim_type") or (state.active_claim_type if state else None)
        case_id = parse.entities.get("case_id") or (state.active_case_id if state else None)
        goal = parse.user_goal or (state.active_goal if state else None)
        return {
            "active_topic": active_topic,
            "active_claim_type": claim_type,
            "active_case_id": str(case_id) if case_id else None,
            "active_goal": goal,
            "known_facts": tuple(sorted(facts)),
        }


class PolicyLayer:
    def authorize(self, *, parse: SemanticParse) -> PolicyDecision:
        if parse.requested_action == "consultar_estado_real" or (parse.requires_tool and parse.topic in {"ticket", "siniestro"}):
            return PolicyDecision(
                requested_action=parse.requested_action,
                tool_required="claim_status_lookup" if parse.topic == "siniestro" else "ticket_status_lookup",
                tool_available=False,
                authorization="blocked",
                fallback="explain_limit_and_offer_next_step",
                reason="No hay herramienta real conectada para consultar estados privados en la demo pública.",
            )
        if parse.confidence < 0.65:
            return PolicyDecision(requested_action=parse.requested_action, authorization="needs_clarification", fallback="ask_clarification", reason="Baja confianza semántica.")
        return PolicyDecision(requested_action=parse.requested_action, authorization="authorized")


class HybridConversationPlanner:
    def plan(self, *, parse: SemanticParse, policy: PolicyDecision, state: PublicConversationState | None) -> PlannerDecision:
        must_not = ("estado_real_del_siniestro", "promesa_de_resolucion", "consulta_a_sistemas", "jerga_interna")
        if parse.intent == "solicitar_derivacion":
            return PlannerDecision(next_action="prepare_handoff", strategy="prepare_handoff_summary_with_context", handoff_target="human_representative", must_include=("resumen_contexto", "proximo_paso"), must_not_include=must_not)
        if policy.authorization == "needs_clarification":
            return PlannerDecision(next_action="ask_clarification", strategy="ask_one_useful_clarification", needs_clarification=True, must_include=("pregunta_concreta",), must_not_include=must_not)
        if policy.authorization == "blocked":
            return PlannerDecision(next_action="explain_limit", strategy="explain_tool_limit_then_orient", tool_request=policy.tool_required, must_include=("limite_de_demo", "proximo_paso"), must_not_include=must_not)
        if parse.signals.frustration in {"medium", "high"} or parse.signals.repetition:
            return PlannerDecision(next_action="repair", strategy="acknowledge_repetition_then_change_strategy", must_include=("reconocimiento", "respuesta_directa"), must_not_include=must_not)
        if parse.intent == "pedir_respuesta_modelo":
            return PlannerDecision(next_action="show_example", strategy="show_client_facing_answer", must_include=("respuesta_modelo",), must_not_include=must_not)
        return PlannerDecision(next_action="answer", strategy="answer_with_contextual_guidance", must_include=("orientacion", "proximo_paso"), must_not_include=must_not)


class NaturalReplyGenerator:
    def generate(self, *, parse: SemanticParse, policy: PolicyDecision, plan: PlannerDecision, state: PublicConversationState | None) -> tuple[str, str, str | None]:
        claim_type = str(parse.entities.get("claim_type") or (state.active_claim_type if state else "") or "")
        case_id = str(parse.entities.get("case_id") or (state.active_case_id if state else "") or "")
        facts = set(parse.known_facts)
        submitted = "denuncia_o_documentacion_cargada" in facts or "paso_previo_realizado" in facts or (state and "denuncia_o_documentacion_cargada" in getattr(state, "known_facts", ()))

        if parse.intent == "saludo":
            return ("Hola 😊 Soy ACA. Puedo orientarte sobre siniestros, documentación, plazos, franquicia o tickets de demo. No tengo conexión real a sistemas del cliente, así que no voy a inventar estados ni datos privados.", "greeting", "Contar qué trámite o duda querés resolver.")
        if parse.intent == "consultar_capacidades":
            suffix = _context_suffix(state=state, claim_type=claim_type, case_id=case_id)
            return ("Puedo ayudarte de tres formas: orientar consultas de siniestros, explicar documentación o plazos, y mostrar cómo prepararía una gestión de ticket en esta demo. No consulto sistemas reales ni invento estados: cuando falta conexión o evidencia, lo aclaro y te digo el próximo paso." + suffix, "capability", "Elegir siniestro, documentación, plazo, franquicia, ticket o derivación.")
        if parse.intent == "consultar_identidad_o_ia":
            suffix = _context_suffix(state=state, claim_type=claim_type, case_id=case_id)
            return ("Soy ACA, un asistente de atención en demo. Tengo una capa conversacional, pero no estoy conectado a una IA externa libre ni a sistemas reales del cliente. Lo que no puedo hacer es consultar un caso real o inventar datos privados. Puedo ayudarte de tres formas: orientar siniestros, explicar documentación o plazos, y mostrar cómo prepararía una gestión de ticket; sí puedo interpretar la consulta, sostener contexto y orientar con límites claros." + suffix, "ai_limit", "Continuar con el caso activo o pedir una respuesta modelo.")
        if parse.intent == "solicitar_derivacion":
            return (_handoff_response(state=state, parse=parse), "handoff_summary", "Derivar con resumen contextual.")
        if plan.next_action == "ask_clarification":
            if parse.signals.confusion != "none":
                return ("Me explico mejor: puedo orientarte, pero necesito ubicar de qué caso hablamos. Si veníamos con un trámite, puedo seguir desde ahí; si no, decime si es choque, cristales, robo parcial, franquicia o un ticket de demo.", "clarification", "Pedir una sola aclaración útil.")
            return ("Para orientarte sin inventar, necesito ubicar el caso. ¿Hablamos de un choque, cristales, robo parcial, franquicia o un ticket de demo?", "clarification", "Pedir una sola aclaración útil.")
        if parse.intent == "informar_paso_realizado":
            return (_already_done_response(claim_type=claim_type or (state.active_claim_type if state else None), state=state), "step_already_done", "Pasar de documentación/denuncia a seguimiento.")
        if parse.intent == "pedir_respuesta_modelo":
            return (_example_response(claim_type=claim_type, case_id=case_id, state=state), "client_example", "Mostrar respuesta modelo sin fingir herramienta real.")
        if parse.intent == "expresar_frustracion" or parse.signals.frustration in {"medium", "high"} or parse.signals.repetition:
            return (_repair_response(claim_type=claim_type, case_id=case_id, state=state), "repair", "Cambiar estrategia y no repetir.")

        if parse.intent == "general_guidance" and case_id:
            return (f"Sigo sobre el ticket {case_id}. En esta demo no puedo consultar el estado real, pero sí puedo mostrarte qué haría ACA: buscar estado actual, responsable, último movimiento y próximo paso. También puedo preparar una respuesta modelo o una derivación con contexto si el caso estuviera trabado.", "ticket_context_followup", f"Mantener contexto del ticket {case_id} y ofrecer seguimiento o derivación.")

        if parse.intent == "general_guidance" and (claim_type or (state and state.active_claim_type)):
            active = claim_type or (state.active_claim_type if state else "")
            return (f"Sigo con el tema de {active}. Para no repetirte opciones sueltas, puedo responder directo sobre plazos, documentación, canal de denuncia, respuesta modelo o derivación con contexto.", "claim_context_followup", f"Continuar sobre {active} con una acción concreta.")

        if parse.intent == "consultar_estado_o_plazo":
            if case_id:
                return ("Te cuento que en esta demo no tengo conexión real al sistema del cliente, así que no puedo ver el estado verdadero del caso. Lo que sí puedo hacer es mostrarte cómo interpretaría la consulta: detecto que querés consultar el ticket " + case_id + " y prepararía la búsqueda de estado actual, responsable y próximo paso 😊", "ticket_status", f"Preparar consulta del ticket {case_id}: estado, responsable y próximo paso.")
            if claim_type == "choque" or (state and state.active_claim_type == "choque"):
                return (_collision_timeline_response(submitted=bool(submitted)), "claim_collision_timeline", "Orientar seguimiento y plazos sin prometer estado real.")
            return ("Si ya cargaste la denuncia y no tenés novedades, lo primero es distinguir el tipo de siniestro y si la documentación quedó completa. En esta demo no puedo consultar el estado real, pero puedo orientarte con plazos informativos y próximo paso. ¿Fue choque, cristales, robo parcial u otro caso?", "claim_status_waiting", "Identificar tipo de siniestro y orientar seguimiento.")

        if parse.intent == "consultar_documentacion":
            return (_documentation_response(claim_type or (state.active_claim_type if state else None)), "claim_documentation", "Responder documentación contextual.")
        if parse.intent == "consultar_canal":
            return (_channel_response(), "claim_channel", "Responder canal de denuncia.")
        if parse.intent == "consultar_concepto_o_reclamo" and (claim_type == "franquicia" or (state and state.active_claim_type == "franquicia")):
            return (_deductible_response(simple=parse.signals.confusion != "none"), "deductible", "Explicar franquicia simple.")
        if parse.intent == "orientar_siniestro" and claim_type == "choque":
            if submitted:
                return (_collision_timeline_response(submitted=True), "claim_collision_followup", "Orientar etapa posterior a denuncia.")
            return ("Lamento lo del choque. Para orientarte bien: si ya cargaste la denuncia, el próximo paso suele ser esperar análisis de documentación, cobertura y mecánica del hecho. Si todavía no la cargaste, se realiza la denuncia administrativa por el canal digital correspondiente y normalmente se piden fotos de los daños y patente, cédula, registro y relato del hecho.", "claim_collision", "Confirmar si la denuncia ya fue cargada y si hubo lesionados.")
        if claim_type == "cristales":
            return ("Para cristales, normalmente se piden fotos donde se vea claramente el daño y una foto de la patente. En siniestros simples, la resolución inicial suele informarse en 24 a 48 horas hábiles, aunque depende del caso y del proveedor.", "claim_glass", "Cargar fotos y seguir derivación de proveedor si corresponde.")
        if claim_type == "robo parcial":
            return ("Para robo parcial, suele necesitarse denuncia policial, detalle de los elementos robados, fotos de los daños y presupuesto de reposición. Si ya cargaste eso y no hay novedades, corresponde pedir seguimiento del estado del trámite.", "claim_theft", "Revisar denuncia policial, documentación y seguimiento.")
        if claim_type == "franquicia":
            return (_deductible_response(simple=False), "deductible", "Explicar franquicia y carta de franquicia.")

        return ("Todavía no tengo suficiente contexto para orientarte bien. Puedo ayudarte con siniestros, documentación, plazos, franquicia o tickets de demo. Contame qué querés resolver y avanzo desde ahí.", "fallback", "Pedir objetivo concreto.")


class OutputSupervisor:
    def review(self, *, response: str, previous_signature: str | None = None) -> SupervisorResult:
        issues: list[str] = []
        low = response.lower()
        if "estoy revisando" in low or "consulté el sistema" in low or "ya verifiqué" in low:
            issues.append("claimed_real_system_lookup")
        if "runtime" in low or "intent" in low or "selected flow" in low:
            issues.append("leaked_internal_jargon")
        sig = _signature(response)
        if previous_signature and sig == previous_signature:
            issues.append("repeated_previous_answer")
        return SupervisorResult(passes=not issues, issues=tuple(issues), requires_rewrite=bool(issues), blocked_reason=issues[0] if issues else None)


class PublicConversationWorkflow:
    def __init__(self) -> None:
        self.semantic = SemanticUnderstandingLayer()
        self.merge = ContextMergeEngine()
        self.policy = PolicyLayer()
        self.planner = HybridConversationPlanner()
        self.generator = NaturalReplyGenerator()
        self.supervisor = OutputSupervisor()

    def run(self, *, message: str, state: PublicConversationState | None, entities: Mapping[str, Any] | None = None) -> ConversationWorkflowResult:
        started = now_ms()
        parse = self.semantic.parse(message=message, state=state, entities=entities)
        merged = self.merge.merge(state=state, parse=parse)
        policy = self.policy.authorize(parse=parse)
        plan = self.planner.plan(parse=parse, policy=policy, state=state)
        text, category, next_step = self.generator.generate(parse=parse, policy=policy, plan=plan, state=state)
        supervisor = self.supervisor.review(response=text, previous_signature=getattr(state, "last_response_signature", None))
        if not supervisor.passes:
            text = _safe_rewrite(text=text, supervisor=supervisor, parse=parse, state=state)
            supervisor = self.supervisor.review(response=text, previous_signature=getattr(state, "last_response_signature", None))
        latency = max(0, now_ms() - started)
        trace_id = make_trace_id(state.conversation_id if state else "public", state.turn_count + 1 if state else 1, message)
        public_trace = {
            "Qué entendí": parse.user_goal,
            "Qué contexto usé": _public_context(state=state, merged=merged),
            "Qué decidí hacer": plan.strategy,
            "Qué límite encontré": policy.reason or "Sin límite operativo relevante.",
        }
        developer_trace = {
            "trace_id": trace_id,
            "session_id": state.conversation_id if state else "public",
            "semantic_parse": parse.to_dict(),
            "state_before": state.to_dict() if state else {},
            "state_after_projection": {k: (list(v) if isinstance(v, tuple) else v) for k, v in merged.items()},
            "planner_decision": plan.to_dict(),
            "policy_decision": policy.to_dict(),
            "guardrail_result": supervisor.to_dict(),
            "tool_requests": [policy.tool_required] if policy.tool_required else [],
            "fallback_used": category in {"fallback", "clarification"},
            "latency_ms": latency,
            "model_used": "deterministic_offline_fallback",
        }
        return ConversationWorkflowResult(
            text=text,
            category=category,
            next_step=next_step,
            semantic_parse=parse.to_dict(),
            policy_decision=policy.to_dict(),
            planner_decision=plan.to_dict(),
            supervisor_result=supervisor.to_dict(),
            public_trace=public_trace,
            developer_trace=developer_trace,
        )


def _detect_claim_type(text: str) -> str | None:
    if contains_any(text, ["choque", "colision", "me chocaron", "accidente"]):
        return "choque"
    if contains_any(text, ["cristal", "vidrio", "parabrisas", "luneta"]):
        return "cristales"
    if contains_any(text, ["robo", "robaron", "rueda", "bateria", "estereo"]):
        return "robo parcial"
    if "franqui" in text or "franquisia" in text:
        return "franquicia"
    return None


def _extract_case_id(text: str) -> str | None:
    match = __import__("re").search(r"(?:ticket|caso|case id|id)\s*#?\s*(\d{3,})", text)
    return match.group(1) if match else None


def _is_greeting(text: str) -> bool:
    return text in {"hola", "buenas", "buen dia", "buenos dias", "buenas tardes", "buenas noches"}


def _short_or_contextual(text: str) -> bool:
    return text in {"bueno", "bue", "ok", "dale", "plazos", "documentacion", "canal", "ayuda", "derivame"} or len(text.split()) <= 3


def _level(text: str, terms: list[str], *, medium: bool) -> str:
    if contains_any(text, terms):
        return "medium" if medium else "low"
    return "none"


def _frustration_level(text: str) -> str:
    if contains_any(text, ["no ayuda", "no estas siendo", "ya me dijiste", "mil veces", "ay dios", "inutil", "no sirve"]):
        return "medium"
    if text.strip() in {"bue", "bueh", "bue...", "bueh..."}:
        return "medium"
    return "none"


def _state_facts(state: PublicConversationState | None) -> tuple[str, ...]:
    if state is None:
        return ()
    facts = list(getattr(state, "known_facts", ()) or ())
    if state.active_case_id:
        facts.append(f"ticket:{state.active_case_id}")
    if state.active_claim_type:
        facts.append(f"tipo_siniestro:{state.active_claim_type}")
    return tuple(dict.fromkeys(facts))


def _context_suffix(*, state: PublicConversationState | None, claim_type: str, case_id: str) -> str:
    if case_id or (state and state.active_case_id):
        active = case_id or state.active_case_id
        return f" Como veníamos con el ticket {active}, puedo seguir con ese contexto y mostrar qué buscaría: estado, responsable y próximo paso."
    if claim_type or (state and state.active_claim_type):
        active = claim_type or state.active_claim_type
        return f" Como veníamos con {active}, puedo seguir con documentación, plazos, canal o derivación."
    return ""


def _collision_timeline_response(*, submitted: bool) -> str:
    if submitted:
        return "Perfecto, entonces ya pasaste la etapa de carga de denuncia o documentación. En un choque, después suele quedar el análisis de cobertura, documentación y mecánica del hecho. En esta demo no puedo ver el estado real del trámite, pero como orientación: si ya pasaron varios días hábiles sin novedad, corresponde pedir seguimiento del caso y confirmar si quedó pendiente algún documento, inspección o derivación a proveedor."
    return "Para un choque, el plazo depende de la etapa. La denuncia debe hacerse dentro de las 72 horas hábiles desde el hecho o desde que tomaste conocimiento. Después, el análisis puede variar porque revisan cobertura, documentación y mecánica del accidente. No conviene prometer fecha exacta de pago, reparación o repuestos porque puede depender de terceros."


def _documentation_response(claim_type: str | None) -> str:
    if claim_type == "choque":
        return "Para el choque, la documentación base suele ser: denuncia administrativa del siniestro, fotos de los daños y de la patente, cédula verde o azul, registro de conducir y, si corresponde, presupuesto de reparación. Si ya la enviaste, el siguiente paso no es volver a cargarla: corresponde esperar análisis o pedir seguimiento si no hubo novedades."
    if claim_type == "cristales":
        return "Para cristales, normalmente se piden fotos donde se vea claramente el daño y una foto de la patente. Según el caso, pueden derivarte a una cristalería de la red o pedir presupuesto si corresponde reintegro."
    if claim_type == "robo parcial":
        return "Para robo parcial, se suele pedir denuncia policial, detalle de elementos robados, fotos de los daños y presupuesto de reposición."
    if claim_type == "franquicia":
        return "Para carta o reclamo de franquicia, generalmente hace falta que el siniestro esté cerrado o aprobado, que exista cobertura de Todo Riesgo con Franquicia, respaldo del monto abonado y datos del tercero si corresponde reclamarle ese importe."
    return "La documentación depende del tipo de siniestro. Si fue choque, cristales o robo parcial, te puedo orientar con el listado específico sin inventar datos del trámite."


def _channel_response() -> str:
    return "La denuncia se realiza por canales digitales según el origen de la póliza: App o Home Banking de Banco Galicia, App Naranja X, Sucursal Digital para ex Sura, y para terceros no asegurados el canal web exclusivo de terceros. Si ya la cargaste por la app, no hace falta volver a denunciar: el próximo paso es seguimiento del estado o documentación pendiente."


def _deductible_response(*, simple: bool) -> str:
    if simple:
        return "Lo explico más simple: la franquicia es la parte del arreglo que paga el asegurado. Si el arreglo supera ese monto, la aseguradora cubre la diferencia según la póliza. Si no fuiste responsable del choque, después puede corresponder pedir carta de franquicia para reclamar ese importe al tercero."
    return "La franquicia es el monto que queda a cargo del asegurado cuando la póliza lo establece. La aseguradora cubre el costo que supere ese valor. Si el siniestro ya fue aprobado y no fuiste responsable, puede corresponder solicitar una carta de franquicia para reclamar ese importe al seguro del tercero."


def _already_done_response(*, claim_type: str | None, state: PublicConversationState | None) -> str:
    if claim_type == "choque" or (state and state.active_claim_type == "choque"):
        return "Perfecto, entonces no tiene sentido repetirte la documentación. Si ya cargaste la denuncia y enviaste los archivos, el próximo punto es seguimiento: confirmar si el caso está en análisis, si quedó documentación pendiente, si fue derivado a inspección/proveedor o si ya tiene una resolución inicial. En esta demo no puedo consultar ese estado real, pero esa sería la ruta correcta."
    return "Perfecto, entonces ya dejamos ese paso como realizado. El siguiente paso es revisar estado, pendiente o derivación. En esta demo no puedo consultar el sistema real, pero puedo preparar el resumen de seguimiento o derivación."


def _handoff_response(*, state: PublicConversationState | None, parse: SemanticParse) -> str:
    pieces = []
    if state and state.active_claim_type:
        pieces.append(f"siniestro: {state.active_claim_type}")
    if state and state.active_case_id:
        pieces.append(f"ticket: {state.active_case_id}")
    facts = list(getattr(state, "known_facts", ()) or []) + list(parse.known_facts)
    clean = [fact.replace("tipo_siniestro:", "tipo de siniestro: ").replace("ticket:", "ticket: ").replace("denuncia_o_documentacion_cargada", "denuncia/documentación cargada").replace("paso_previo_realizado", "el cliente indica que ya realizó el paso solicitado") for fact in dict.fromkeys(facts)]
    summary = "; ".join([*pieces, *clean]) or "consulta sin datos suficientes todavía"
    return f"Entiendo. Si querés hablar con una persona, lo correcto es derivar con contexto para que no tengas que repetir todo. Resumen para derivación: {summary}. Motivo: el cliente solicita seguimiento/ayuda y prefiere atención humana. Próximo paso: que un representante revise estado, pendientes y próxima acción disponible."


def _example_response(*, claim_type: str, case_id: str, state: PublicConversationState | None) -> str:
    if case_id or (state and state.active_case_id):
        active = case_id or state.active_case_id
        return f"Claro. Una respuesta modelo para el cliente sería: “Voy a revisar el ticket {active} para confirmarte el estado del caso, en qué instancia está, quién lo tiene asignado y cuál es el próximo paso. Si figura documentación pendiente o una derivación abierta, te lo voy a indicar con el canal correspondiente para que no tengas que volver a consultar por lo mismo”. En esta demo no puedo hacer esa consulta real, pero esa es la respuesta operativa esperada."
    if claim_type == "choque" or (state and state.active_claim_type == "choque"):
        return "Claro. Una respuesta modelo sería: “Veo que ya cargaste la denuncia por choque desde la app. El trámite normalmente pasa a análisis de documentación, cobertura y mecánica del hecho. Si ya enviaste todo y seguís sin novedades, vamos a pedir seguimiento para confirmar si quedó algún pendiente, derivación o próximo paso disponible”."
    return "Claro. La respuesta modelo debería reconocer lo que el cliente ya hizo, explicar el límite si no hay acceso real al sistema y cerrar con el próximo paso concreto, no repetir instrucciones genéricas."


def _repair_response(*, claim_type: str, case_id: str, state: PublicConversationState | None) -> str:
    if case_id or (state and state.active_case_id):
        active = case_id or state.active_case_id
        return f"Tenés razón: repetir el límite de la demo no ayuda. Para el ticket {active}, una respuesta de atención útil debería preparar esto: consultar estado actual, área responsable, último movimiento y próximo paso. Como no tengo herramienta real conectada, no puedo dar ese estado; sí puedo mostrar la respuesta modelo o preparar una derivación con contexto."
    if claim_type == "choque" or (state and state.active_claim_type == "choque"):
        return "Tenés razón: no te sirve que repita opciones. Bajándolo a tu caso: si ya cargaste la denuncia por choque y enviaste documentación, ahora corresponde seguimiento del trámite. Hay que revisar si está en análisis, pendiente de documentación, derivado a inspección/proveedor o aprobado/rechazado. En esta demo no puedo ver ese estado real, pero puedo prepararte el resumen para derivación."
    return "Tenés razón: responder genérico no ayuda. Cambio de estrategia: decime si querés que prepare una respuesta modelo al cliente, un resumen para derivación o una explicación breve del próximo paso."


def _public_context(*, state: PublicConversationState | None, merged: Mapping[str, Any]) -> str:
    facts = list(merged.get("known_facts") or [])
    if facts:
        return ", ".join(str(f).replace("tipo_siniestro:", "tipo de siniestro: ").replace("ticket:", "ticket: ") for f in facts[:4])
    if state and state.active_topic:
        return str(state.active_topic)
    return "Sin contexto previo relevante."


def _signature(text: str) -> str:
    words = normalize_text(text).split()
    return " ".join(words[:22])


def _safe_rewrite(*, text: str, supervisor: SupervisorResult, parse: SemanticParse, state: PublicConversationState | None) -> str:
    if "repeated_previous_answer" in supervisor.issues:
        if state and state.active_claim_type == "choque":
            return "Cambio la respuesta para no repetir: si ya cargaste la denuncia por choque, ahora la conversación debería ir a seguimiento del trámite, no a documentación inicial. En esta demo no puedo ver el estado real, pero sí puedo resumir el caso para derivarlo o explicarte los plazos informativos."
        return "Cambio la respuesta para no repetir: puedo preparar una respuesta modelo, explicar el límite real de la demo o armar una derivación con el contexto acumulado."
    return "Para no inventar ni mostrar información interna, te respondo con el límite claro: esta demo puede orientar y preparar el próximo paso, pero no consulta sistemas reales."
