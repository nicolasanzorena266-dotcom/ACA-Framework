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
        elif state.plan:
            response = _response_for_plan(state.plan)
            if "explain_missing_third_party_report" in state.plan:
                response += " Si el tercero todavía no hizo la denuncia, el avance puede demorarse porque las compañías necesitan cruzar y validar la información del siniestro."
        elif state.active_mission and state.active_mission.get("type") == "auto_claim_guidance":
            response = _response_after_slots(state)
        else:
            response = "Necesito un poco más de contexto para orientarte sin inventar."
        return state.evolve(self.name, response=response)


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
        return "Te oriento. Primero necesito confirmar: hubo lesionados?"
    if "ask_user_role" in plan:
        return "Gracias. Ahora necesito confirmar: sos asegurado de Galicia o tercero damnificado?"
    return "Te oriento con el siniestro y el proximo paso segun lo que ya confirmaste."


def _response_after_slots(state: CognitiveState) -> str:
    facts = dict(state.facts)
    injuries = facts.get("injuries")
    user_role = facts.get("user_role")
    mission = state.active_mission or {}
    next_act = mission.get("next_act")
    if next_act == "clarify_fact_revision":
        return "Entiendo que queres corregir algo, pero necesito que me digas que dato cambiamos: lesionados, rol, denuncia o documentacion?"
    if next_act == "prioritize_injury_assistance":
        return "Tomo la correccion: hubo lesionados. En ese caso conviene priorizar asistencia y derivacion con contexto antes de avanzar con una orientacion general."
    if next_act == "check_claim_report_loaded":
        if facts.get("claim_report_loaded") is False:
            return "Tomo la correccion: la denuncia todavia no esta cargada. Para avanzar, primero necesitamos resolver ese paso antes de seguir con la documentacion."
        return "Con esos datos, ya puedo avanzar. Para orientar el proximo paso necesito saber si la denuncia ya esta cargada."
    if next_act == "check_documentation_available":
        return "Tomo que la denuncia ya esta cargada. No te la vuelvo a pedir; ahora confirmemos si tenes toda la documentacion."
    if next_act == "provide_next_step_guidance":
        return "Perfecto. Tomo que la denuncia ya esta cargada y que tenes la documentacion. Ya podemos avanzar con seguimiento del tramite o preparar un resumen para que una persona continue sin que repitas todo."
    if injuries is False and user_role == "insured":
        return "Perfecto. Tomo que no hubo lesionados y que sos asegurado. Con eso podemos avanzar por la orientacion del siniestro sin volver a pedir esos datos."
    if injuries is False and user_role == "third_party":
        return "Perfecto. Tomo que no hubo lesionados y que sos tercero damnificado. Con eso puedo orientarte sin reiniciar el flujo."
    if injuries is True:
        return "Tomo que hubo lesionados. En ese caso conviene priorizar asistencia y derivacion con contexto antes de avanzar con una orientacion general."
    return "Gracias. Ya tome los datos confirmados y puedo continuar sin volver a pedirlos."
