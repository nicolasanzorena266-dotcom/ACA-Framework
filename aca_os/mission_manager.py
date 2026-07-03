from aca_kernel.core.state import CognitiveState
from aca_kernel.core.events import Event

def normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    for a,b in {"á":"a","é":"e","í":"i","ó":"o","ú":"u","ñ":"n"}.items():
        text = text.replace(a,b)
    return text

class MissionManager:
    def before_kernel(self, event: Event, state: CognitiveState | None = None) -> CognitiveState:
        current = state or CognitiveState()
        if current.active_mission:
            return current
        text = normalize_text(str(event.payload))
        if any(x in text for x in ["me chocaron", "choque", "chocaron", "accidente", "siniestro"]):
            mission = {
                "type": "auto_claim_guidance",
                "goal": "orientar correctamente al usuario sobre un siniestro automotor",
                "status": "in_progress",
                "progress": 0.10,
                "blockers": ["injuries_unknown", "user_role_unknown"],
                "missing": ["injuries", "user_role"],
            }
        else:
            mission = {
                "type": "general_orientation",
                "goal": "comprender la necesidad del usuario y orientar sin inventar",
                "status": "in_progress",
                "progress": 0.05,
                "blockers": ["need_more_context"],
                "missing": ["user_need"],
            }
        return current.evolve("MISSION_CREATE", active_mission=mission)

    def after_kernel(self, state: CognitiveState) -> CognitiveState:
        if not state.active_mission:
            return state
        mission = dict(state.active_mission)
        if state.response:
            mission["progress"] = max(float(mission.get("progress", 0)), 0.75)
        return state.evolve("MISSION_UPDATE", active_mission=mission)
