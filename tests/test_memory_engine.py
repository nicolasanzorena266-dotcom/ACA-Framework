from aca_kernel.core.state import CognitiveState
from aca_os.memory_engine import MemoryEngine


def test_memory_engine_consolidates_mission_and_event_type():
    engine = MemoryEngine()
    state = CognitiveState(
        facts={"event_type": "vehicle_collision"},
        active_mission={"type": "auto_claim_guidance"},
        policy_result={"decision": "ALLOW"},
        tool_evidence={"cleas": {"name": "CLEAS"}},
    )

    consolidated = engine.consolidate(state)

    assert consolidated["last_mission_type"] == "auto_claim_guidance"
    assert consolidated["last_event_type"] == "vehicle_collision"
    assert engine.semantic["last_mission_type"] == "auto_claim_guidance"
    assert len(engine.episodic) == 3


def test_memory_engine_returns_relevant_memory_for_state():
    engine = MemoryEngine()
    engine.remember_semantic("preferred_style", "simple")

    state = CognitiveState(active_mission={"type": "auto_claim_guidance"})
    relevant = engine.relevant_for_state(state)

    assert relevant["preferred_style"] == "simple"
    assert relevant["current_mission_type"] == "auto_claim_guidance"