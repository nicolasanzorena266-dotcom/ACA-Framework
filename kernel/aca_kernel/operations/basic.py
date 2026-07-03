from typing import Any, Dict
from aca_kernel.core.operation import CognitiveOperation
from aca_kernel.core.contract import OperationContract
from aca_kernel.core.state import CognitiveState
from aca_kernel.core.events import Event

def normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    for a,b in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n"}.items():
        text = text.replace(a,b)
    return text

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
        text = normalize_text(str(event.payload))
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
        if state.hypotheses.get("needs_claim_guidance", 0) > 0.7:
            plan.extend(["ask_if_injuries", "ask_user_role"])
        if state.hypotheses.get("process_may_be_delayed_by_missing_third_party_report", 0) > 0.7:
            plan.append("explain_missing_third_party_report")
        return state.evolve(self.name, goal="reduce_uncertainty_and_orient_user", plan=plan)

class Generate(CognitiveOperation):
    name = "GENERATE"
    contract = OperationContract(name, can_modify=["response"])
    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        if state.selected_program == "greeting":
            response = "Hola. Contame qué necesitás y te oriento."
        elif state.plan:
            response = "Te oriento. Primero necesito confirmar dos datos porque cambian el circuito: ¿hubo lesionados? ¿Sos asegurado de Galicia o sos tercero damnificado?"
            if "explain_missing_third_party_report" in state.plan:
                response += " Si el tercero todavía no hizo la denuncia, el avance puede demorarse porque las compañías necesitan cruzar y validar la información del siniestro."
        else:
            response = "Necesito un poco más de contexto para orientarte sin inventar."
        return state.evolve(self.name, response=response)

class Verify(CognitiveOperation):
    name = "VERIFY"
    contract = OperationContract(name, can_modify=["response"])
    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        return state.evolve(self.name, response=state.response)
