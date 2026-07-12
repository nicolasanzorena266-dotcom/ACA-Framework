from aca_core.text import normalize_text
from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.conversation_state import ConversationState


class MissionManager:
    def before_kernel(
        self,
        event: Event,
        state: CognitiveState | None = None,
        *,
        conversation_state: ConversationState | None = None,
    ) -> CognitiveState:
        current = state or CognitiveState()
        if current.active_mission:
            if conversation_state is not None and conversation_state.active_mission == current.active_mission:
                return current.evolve(
                    "MISSION_LOAD_FROM_CONVERSATION_STATE",
                    active_mission=dict(current.active_mission),
                )
            return current
        if conversation_state is not None and conversation_state.active_mission:
            return current.evolve(
                "MISSION_LOAD_FROM_CONVERSATION_STATE",
                active_mission=dict(conversation_state.active_mission),
            )
        if _planned_flow(current) == "knowledge_lookup":
            action_plan = current.facts.get("zero_cost_action_plan", {})
            payload = action_plan.get("payload", {}) if isinstance(action_plan, dict) else {}
            concept_key = payload.get("tool_key") if isinstance(payload, dict) else None
            mission = {
                "type": "knowledge_lookup",
                "goal": "explicar un concepto usando evidencia estructurada",
                "status": "in_progress",
                "lifecycle_status": "initialized",
                "progress": 0.25,
                "next_act": "provide_concept_explanation",
                "blockers": [],
                "missing": [],
            }
            if concept_key:
                mission["concept_key"] = concept_key
            return current.evolve("MISSION_CREATE", active_mission=mission)

        text = normalize_text(event.payload)
        if _planned_flow(current) == "guided_process" or any(x in text for x in ["me chocaron", "choque", "chocaron", "accidente", "siniestro", "denuncia"]):
            mission = {
                "type": "auto_claim_guidance",
                "goal": "orientar correctamente al usuario sobre un siniestro automotor",
                "status": "in_progress",
                "lifecycle_status": "initialized",
                "progress": 0.10,
                "next_act": "ask_injuries",
                "blockers": ["injuries_unknown", "user_role_unknown"],
                "missing": ["injuries", "user_role"],
            }
        else:
            mission = {
                "type": "general_orientation",
                "goal": "comprender la necesidad del usuario y orientar sin inventar",
                "status": "in_progress",
                "lifecycle_status": "initialized",
                "progress": 0.05,
                "next_act": "ask_user_need",
                "blockers": ["need_more_context"],
                "missing": ["user_need"],
            }
        return current.evolve("MISSION_CREATE", active_mission=mission)

    def after_kernel(
        self,
        state: CognitiveState,
        *,
        conversation_state: ConversationState | None = None,
    ) -> CognitiveState:
        if not state.active_mission:
            return state
        mission = dict(state.active_mission)
        if state.response:
            mission["progress"] = max(float(mission.get("progress", 0)), 0.75)
        return state.evolve("MISSION_UPDATE", active_mission=mission)


def _planned_flow(state: CognitiveState) -> str | None:
    execution_plan = state.facts.get("zero_cost_execution_plan")
    if not isinstance(execution_plan, dict):
        return None
    flow = execution_plan.get("flow")
    return str(flow) if flow else None
