from typing import Any, Dict

from aca_core.text import normalize_text
from aca_kernel.core.contract import OperationContract
from aca_kernel.core.events import Event
from aca_kernel.core.operation import CognitiveOperation
from aca_kernel.core.state import CognitiveState


class Observe(CognitiveOperation):
    name = "OBSERVE"
    contract = OperationContract(name, can_modify=["facts"])

    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        facts = dict(state.facts)
        facts["last_event_type"] = event.type
        facts["last_raw_payload"] = event.payload
        return state.evolve(self.name, facts=facts)


class Extract(CognitiveOperation):
    name = "EXTRACT"
    contract = OperationContract(name, can_modify=["entities"])

    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        text = normalize_text(event.payload)
        entities = dict(state.entities)
        if any(x in text for x in ["me chocaron", "choque", "chocaron", "accidente", "siniestro"]):
            entities["event"] = "vehicle_collision"
        if "ayer" in text:
            entities["date"] = "relative:yesterday"
        if "tercero" in text:
            entities["actor_secondary"] = "third_party"
        if "no hizo la denuncia" in text or "no denuncio" in text:
            entities["third_party_report"] = "missing"
        return state.evolve(self.name, entities=entities)


class Normalize(CognitiveOperation):
    name = "NORMALIZE"
    contract = OperationContract(name, can_modify=["facts"])

    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        facts = dict(state.facts)
        if state.entities.get("event") == "vehicle_collision":
            facts["event_type"] = "vehicle_collision"
        if state.entities.get("date") == "relative:yesterday":
            facts["event_date"] = "relative:yesterday"
        if state.entities.get("third_party_report") == "missing":
            facts["third_party_reported"] = False
        return state.evolve(self.name, facts=facts)


class Relate(CognitiveOperation):
    name = "RELATE"
    contract = OperationContract(name, can_modify=["relations"])

    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        relations = list(state.relations)
        if state.facts.get("event_type") == "vehicle_collision" and state.entities.get("actor_secondary") == "third_party":
            relations.append({"subject": "vehicle_collision", "relation": "involves", "object": "third_party"})
        return state.evolve(self.name, relations=relations)


class Infer(CognitiveOperation):
    name = "INFER"
    contract = OperationContract(name, can_modify=["hypotheses"])

    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        hypotheses = dict(state.hypotheses)
        if state.facts.get("event_type") == "vehicle_collision":
            hypotheses["needs_claim_guidance"] = 0.92
        if state.facts.get("third_party_reported") is False:
            hypotheses["process_may_be_delayed_by_missing_third_party_report"] = 0.90
        return state.evolve(self.name, hypotheses=hypotheses)


class Score(CognitiveOperation):
    name = "SCORE"
    contract = OperationContract(name, can_modify=["scores"])

    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        return state.evolve(self.name, scores={"overall_confidence": max(state.hypotheses.values()) if state.hypotheses else 0.0})


class Plan(CognitiveOperation):
    name = "PLAN"
    contract = OperationContract(name, can_modify=["goal", "plan"])

    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        plan = []
        if state.hypotheses.get("needs_claim_guidance", 0) > 0.7 or (state.active_mission or {}).get("type") == "auto_claim_guidance":
            pending_slots = _pending_slots(state, context or {})
            if "injuries" in pending_slots:
                plan.append("ask_if_injuries")
            if "user_role" in pending_slots:
                plan.append("ask_user_role")
        if state.hypotheses.get("process_may_be_delayed_by_missing_third_party_report", 0) > 0.7:
            plan.append("explain_missing_third_party_report")
        return state.evolve(self.name, goal="reduce_uncertainty_and_orient_user", plan=plan)


class Generate(CognitiveOperation):
    name = "GENERATE"
    contract = OperationContract(name, can_modify=["response"])

    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        tool_response = _response_from_tool_evidence(context or {})
        if tool_response:
            response = tool_response
        elif state.selected_program == "greeting":
            response = "Hola. Contame qué necesitás y te oriento."
        elif state.active_mission and state.active_mission.get("type") == "auto_claim_guidance" and _conversation_act_controls_response(state):
            response = _response_after_slots(state)
        elif _response_from_conversational_response_plan(state):
            response = _response_from_conversational_response_plan(state) or ""
        elif state.plan:
            response = _response_for_plan(state.plan)
            if "explain_missing_third_party_report" in state.plan:
                response += " Si el tercero todavía no hizo la denuncia, el avance puede demorarse porque las compañías necesitan cruzar y validar la información del siniestro."
        elif state.active_mission and state.active_mission.get("type") == "auto_claim_guidance":
            response = _response_after_slots(state)
        else:
            response = "Necesito un poco más de contexto para orientarte sin inventar."
        return state.evolve(self.name, response=_enforce_cognitive_opacity(response))


class Verify(CognitiveOperation):
    name = "VERIFY"
    contract = OperationContract(name, can_modify=["response"])

    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        return state.evolve(self.name, response=state.response)


def _response_from_tool_evidence(context: Dict[str, Any]) -> str | None:
    policy_result = context.get("policy_result")
    if not isinstance(policy_result, dict) or policy_result.get("decision") != "USE_TOOL":
        return None

    tool_evidence = context.get("tool_evidence")
    if not isinstance(tool_evidence, dict) or not tool_evidence:
        return None

    tool_key = policy_result.get("tool_key")
    if tool_key and isinstance(tool_evidence.get(tool_key), dict):
        evidence = tool_evidence[tool_key]
    else:
        evidence = next((value for value in tool_evidence.values() if isinstance(value, dict)), None)
    if not evidence:
        return None

    explanation = evidence.get("simple_explanation") or evidence.get("summary")
    if not explanation:
        return None

    name = str(evidence.get("name") or tool_key or "El concepto")
    response = f"{name}: {explanation}"

    rules = evidence.get("agent_rules")
    if isinstance(rules, list) and rules:
        response += f" Importante: {rules[0]}"
    return response


def _response_from_conversational_response_plan(state: CognitiveState) -> str | None:
    plan = _conversation_response_plan(state)
    if not plan:
        return None
    primary = dict(plan.get("primary_user_need") or {})
    primary_key = str(primary.get("key") or "")
    secondary = [dict(item) for item in plan.get("secondary_needs") or [] if isinstance(item, dict)]
    required = [dict(item) for item in plan.get("required_information") or [] if isinstance(item, dict)]
    if primary_key == "vehicle_repair_authorization":
        parts = [
            "Sobre arreglar el auto: la clave es no perjudicar la evaluacion del siniestro.",
            "En general conviene esperar la autorizacion o indicacion de la aseguradora antes de repararlo; si necesitas moverlo por seguridad, conserva fotos, presupuesto y comprobantes del dano.",
        ]
        if any(item.get("key") == "photo_upload_status" for item in secondary):
            parts.append("Sobre las fotos: si no estas seguro de haberlas enviado, conviene revisar si figuran cargadas o tenerlas listas para volver a adjuntarlas.")
        question = _question_sentence(required)
        if question:
            parts.append(question)
        return " ".join(parts)
    if primary_key == "claim_contact_progress":
        parts = [
            "Sobre cuando te van a contactar: mas que prometer una fecha, lo importante es verificar que el caso este siguiendo el circuito esperado.",
            "Para eso conviene revisar si la denuncia esta cargada, si la documentacion quedo completa y si el canal muestra alguna observacion.",
        ]
        question = _question_sentence(required)
        if question:
            parts.append(question)
        return " ".join(parts)
    if primary_key == "photo_requirement_confidence":
        parts = [
            "Que no te hayan pedido fotos no significa necesariamente que hiciste algo mal.",
            "Depende del tipo de siniestro y del estado del tramite; lo importante es revisar si el canal muestra fotos pendientes u observaciones.",
        ]
        question = _question_sentence(required)
        if question:
            parts.append(question)
        return " ".join(parts)
    if primary_key == "photo_upload_status":
        parts = [
            "Sobre las fotos: lo importante es confirmar si quedaron cargadas y si el tramite muestra alguna observacion."
        ]
        question = _question_sentence(required)
        if question:
            parts.append(question)
        return " ".join(parts)
    if primary_key == "claim_report_status":
        parts = ["Sobre la denuncia: si ya esta cargada, el paso siguiente suele ser revisar documentacion y seguimiento del tramite."]
        question = _question_sentence(required)
        if question:
            parts.append(question)
        return " ".join(parts)
    if primary_key == "claim_status_or_payment":
        parts = [
            "Sobre los tiempos: suelen depender del estado de la denuncia, la documentacion y la validacion del siniestro.",
            "Si el tramite esta completo, lo util es revisar si el canal muestra observaciones o novedades pendientes.",
        ]
        question = _question_sentence(required)
        if question:
            parts.append("Respecto a tu denuncia, " + _lower_first(question))
        return " ".join(parts)
    if primary_key == "documentation_guidance":
        parts = [
            "Para documentacion del siniestro, normalmente conviene tener fotos del dano, presupuesto o comprobante del taller, datos del otro vehiculo y cualquier constancia que te haya pedido el canal.",
            "Eso ayuda a que la revision avance con menos idas y vueltas.",
        ]
        question = _question_sentence(required)
        if question:
            parts.append(question)
        return " ".join(parts)
    if required and primary_key in {"auto_claim_guidance", "understand_user_need"}:
        return _question_sentence(required)
    return None


def _conversation_response_plan(state: CognitiveState) -> Dict[str, Any]:
    trace = dict(state.facts.get("conversation_response_plan") or {})
    plan = trace.get("plan")
    if isinstance(plan, dict):
        return dict(plan)
    return trace


def _question_sentence(required_information: list[Dict[str, Any]]) -> str:
    if not required_information:
        return ""
    item = required_information[0]
    question = str(item.get("question") or "").strip()
    purpose = str(item.get("purpose") or "").strip()
    if not question:
        return ""
    if purpose:
        return f"{question} Asi puedo {purpose}."
    return question


def _pending_slots(state: CognitiveState, context: Dict[str, Any]) -> list[str]:
    conversation_state = context.get("conversation_state")
    if isinstance(conversation_state, dict):
        slots = conversation_state.get("slots")
        if isinstance(slots, dict):
            pending = [
                str(name)
                for name, slot in slots.items()
                if isinstance(slot, dict) and slot.get("status") in {"pending", "partially_filled"}
            ]
            if pending:
                return pending

    mission = state.active_mission or {}
    mission_slots = mission.get("slots")
    if isinstance(mission_slots, dict):
        return [
            str(name)
            for name, slot in mission_slots.items()
            if isinstance(slot, dict) and slot.get("status") in {"pending", "partially_filled"}
        ]

    missing = mission.get("missing")
    if isinstance(missing, list) and missing:
        return [str(slot) for slot in missing]
    if mission.get("type") == "auto_claim_guidance":
        return ["injuries", "user_role"]
    return []


def _response_for_plan(plan: list[str]) -> str:
    if "ask_if_injuries" in plan:
        return "Te oriento. Hubo lesionados? Ese dato define si hay que priorizar asistencia o derivacion antes del tramite."
    if "ask_user_role" in plan:
        return "Gracias. Sos asegurado de Galicia o tercero damnificado? Asi puedo orientarte por el circuito que corresponde a tu rol."
    return "Te oriento con el siniestro y el proximo paso segun lo que ya confirmaste."


def _conversation_act_controls_response(state: CognitiveState) -> bool:
    strategy = _conversation_goal_strategy(state)
    return strategy in {
        "ask_clarification",
        "deepen",
        "repair",
        "simplify",
        "summarize",
        "switch_topic",
        "close",
    }


def _response_after_slots(state: CognitiveState) -> str:
    facts = dict(state.facts)
    injuries = facts.get("injuries")
    user_role = facts.get("user_role")
    mission = state.active_mission or {}
    next_act = mission.get("next_act")
    strategy = _conversation_goal_strategy(state)
    if strategy == "simplify":
        return _simple_mission_response(state)
    if strategy == "summarize":
        return _recap_acknowledgement(state)
    if strategy == "switch_topic":
        return _topic_recovery_response(state)
    if strategy == "deepen":
        return _deepening_response(state)
    if strategy == "ask_clarification":
        return "Necesito una aclaracion concreta para cumplir lo que pediste: que dato cambiamos, lesionados, rol, denuncia o documentacion?"
    if strategy == "close":
        return "Listo, dejo la conversacion pausada con los datos confirmados guardados."
    if next_act == "clarify_fact_revision":
        return "Entiendo que queres corregir algo, pero necesito que me digas que dato cambiamos: lesionados, rol, denuncia o documentacion?"
    if next_act == "prioritize_injury_assistance":
        return "Tomo la correccion: hubo lesionados. En ese caso conviene priorizar asistencia y derivacion con contexto antes de avanzar con una orientacion general."
    if next_act == "check_claim_report_loaded":
        if facts.get("claim_report_loaded") is False:
            return "Tomo la correccion: la denuncia todavia no esta cargada. Para avanzar, primero necesitamos resolver ese paso antes de seguir con la documentacion."
        return "Con esos datos puedo orientarte mejor. La denuncia ya esta cargada? Asi se si corresponde completar la carga o revisar documentacion."
    if next_act == "check_documentation_available":
        return "La denuncia ya esta cargada. Tenes toda la documentacion? Asi puedo ver si corresponde seguimiento o preparar el resumen del tramite."
    if next_act == "provide_next_step_guidance":
        return "Perfecto. La denuncia esta cargada y tenes la documentacion. El siguiente paso util es revisar seguimiento del tramite o preparar un resumen para derivacion."
    if injuries is False and user_role == "insured":
        return "Perfecto. Con no hubo lesionados y sos asegurado, puedo orientarte por el circuito del siniestro."
    if injuries is False and user_role == "third_party":
        return "Perfecto. Con no hubo lesionados y sos tercero damnificado, puedo orientarte sobre el tramite que corresponde."
    if injuries is True:
        return "Tomo que hubo lesionados. En ese caso conviene priorizar asistencia y derivacion con contexto antes de avanzar con una orientacion general."
    return "Gracias. Con los datos confirmados puedo indicarte el siguiente paso util."


def _conversation_goal_strategy(state: CognitiveState) -> str:
    goal_trace = dict(state.facts.get("conversation_goal") or {})
    goal = dict(goal_trace.get("goal") or goal_trace)
    strategy = dict(goal.get("strategy") or {})
    return str(strategy.get("name") or "")


def _conversation_goal_response_plan(state: CognitiveState) -> Dict[str, Any]:
    goal_trace = dict(state.facts.get("conversation_goal") or {})
    goal = dict(goal_trace.get("goal") or goal_trace)
    strategy = dict(goal.get("strategy") or {})
    response_plan = strategy.get("response_plan")
    return dict(response_plan) if isinstance(response_plan, dict) else {}


def _simple_mission_response(state: CognitiveState) -> str:
    response_plan = _conversation_goal_response_plan(state)
    next_act = response_plan.get("mission_next_act") or (state.active_mission or {}).get("next_act")
    if next_act == "ask_injuries":
        return "Mas simple: primero necesito saber si hubo lesionados."
    if next_act == "ask_user_role":
        return "Mas simple: ahora necesito saber si sos asegurado de Galicia o tercero damnificado."
    if next_act == "check_claim_report_loaded":
        return "Mas simple: con lo confirmado, el proximo dato es si la denuncia ya esta cargada."
    if next_act == "check_documentation_available":
        return "Mas simple: ya tomo la denuncia cargada; ahora falta confirmar si tenes toda la documentacion."
    if next_act == "provide_next_step_guidance":
        return "Mas simple: ya estan los datos principales y podemos avanzar al seguimiento o preparar un resumen."
    return "Mas simple: sigo con la misma conversacion y uso lo que ya confirmaste para no empezar de cero."


def _recap_acknowledgement(state: CognitiveState) -> str:
    response_plan = _conversation_goal_response_plan(state)
    focus = dict(response_plan.get("available_focus") or {})
    topic_summary = str(focus.get("summary") or "").strip()
    if topic_summary:
        return "Resumen breve: " + topic_summary + "."
    facts = dict(response_plan.get("confirmed_facts") or state.facts)
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
    if not known:
        return "Registro que queres un resumen. Todavia no tengo suficientes datos confirmados para resumir sin inventar."
    return "Resumen breve de lo confirmado: " + "; ".join(known) + "."


def _deepening_response(state: CognitiveState) -> str:
    response_plan = _conversation_goal_response_plan(state)
    next_act = response_plan.get("mission_next_act") or (state.active_mission or {}).get("next_act")
    facts = dict(response_plan.get("confirmed_facts") or state.facts)
    if next_act == "check_claim_report_loaded":
        return "Mas detalle: con lesionados y rol ya confirmados, el siguiente punto es la denuncia. Ese dato cambia si podemos avanzar a documentacion o si primero hay que completar la carga."
    if next_act == "check_documentation_available":
        return "Mas detalle: como la denuncia ya figura cargada, ahora importa la documentacion. Tenerla completa permite preparar seguimiento o derivar con contexto sin repetir datos."
    if facts.get("injuries") is True:
        return "Mas detalle: al haber lesionados, la prioridad cambia. Antes de una orientacion administrativa conviene asegurar asistencia y derivacion con todo el contexto disponible."
    if facts.get("claim_report_loaded") is True or facts.get("documentation_available") is True:
        return "Mas detalle: con lo que ya confirmaste, conviene revisar si el tramite muestra observaciones y tener a mano fotos, presupuesto y comprobantes para responder rapido si los piden."
    return "Mas detalle: sobre fotos y presupuesto, lo importante es conservar evidencia clara del dano antes de reparar y tenerla lista por si el canal la solicita."


def _topic_recovery_response(state: CognitiveState) -> str:
    response_plan = _conversation_goal_response_plan(state)
    focus = dict(response_plan.get("available_focus") or {})
    direction = str(focus.get("navigation_direction") or response_plan.get("topic_navigation_direction") or "")
    topic = focus.get("summary") or focus.get("active_topic") or focus.get("active_mission_type") or "la orientacion actual"
    next_act = response_plan.get("mission_next_act") or (state.active_mission or {}).get("next_act")
    if direction == "new_topic":
        return f"Dale, contame mas sobre este tema: {topic}."
    if next_act == "check_claim_report_loaded":
        return f"Retomo la denuncia: {topic}. El siguiente dato util es confirmar si la denuncia ya esta cargada."
    return f"Retomo el tema anterior: {topic}."


def _enforce_cognitive_opacity(response: str) -> str:
    replacements = {
        "No te la vuelvo a pedir; ": "",
        "no te vuelvo a pedir": "ya quedo registrado",
        "sin volver a pedir esos datos": "con esos datos",
        "sin reiniciar el flujo": "sobre el tramite",
        "sin reiniciar la conversacion": "desde ese punto",
        "sin reiniciarla": "desde ese punto",
        "Mantengo la mision actual": "Retomo el tema",
        "mantengo el foco": "retomo el tema",
        "Cambio el foco: ": "",
        "dejo suspendido lo anterior y ": "",
        "Voy a cambiar de estrategia": "",
        "Para no girar sobre lo mismo": "",
        "No voy a repetir": "",
        "conversation plan": "seguimiento",
        "conversation goal": "objetivo",
        "estado conversacional": "contexto",
        "runtime": "sistema",
        "planificacion": "organizacion",
        "planificación": "organizacion",
    }
    cleaned = str(response)
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    cleaned = _remove_internal_sentences(cleaned)
    return " ".join(cleaned.split())


def _lower_first(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    return value[:1].lower() + value[1:]


def _remove_internal_sentences(response: str) -> str:
    forbidden = (
        "sin reiniciar",
        "mantengo el foco",
        "mision activa",
        "misión activa",
        "misma mision",
        "misma misión",
        "conversation plan",
        "conversation goal",
        "slot",
        "estado conversacional",
        "runtime",
        "planificacion",
        "planificación",
    )
    sentences = [part.strip() for part in str(response or "").split(".") if part.strip()]
    kept = [
        sentence
        for sentence in sentences
        if not any(phrase in normalize_text(sentence) for phrase in forbidden)
    ]
    if kept:
        suffix = "." if str(response).strip().endswith(".") else ""
        return ". ".join(kept) + suffix
    return ""
