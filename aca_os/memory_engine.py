from dataclasses import dataclass, field
from typing import Any, Dict, List

from aca_kernel.core.state import CognitiveState


@dataclass(frozen=True)
class MemoryRecord:
    key: str
    value: Any
    source: str
    relevance: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "source": self.source,
            "relevance": self.relevance,
        }


class MemoryEngine:
    """ACA OS memory system.

    Working memory lives during the active mission.
    Episodic memory stores relevant events.
    Semantic memory stores stable reusable knowledge.
    Procedural memory stores reusable resolution patterns.
    """

    def __init__(self):
        self.working: Dict[str, Any] = {}
        self.episodic: List[MemoryRecord] = []
        self.semantic: Dict[str, Any] = {}
        self.procedural: Dict[str, Any] = {}

    def remember_working(self, key: str, value: Any) -> None:
        self.working[key] = value

    def remember_semantic(self, key: str, value: Any) -> None:
        self.semantic[key] = value

    def remember_episodic(self, key: str, value: Any, source: str, relevance: float = 1.0) -> None:
        self.episodic.append(
            MemoryRecord(
                key=key,
                value=value,
                source=source,
                relevance=relevance,
            )
        )

    def clear_working(self) -> None:
        self.working.clear()

    def consolidate(self, state: CognitiveState) -> Dict[str, Any]:
        consolidated: Dict[str, Any] = {}

        if state.active_mission:
            mission_type = state.active_mission.get("type")
            if mission_type:
                consolidated["last_mission_type"] = mission_type
                self.remember_semantic("last_mission_type", mission_type)
                self.remember_episodic(
                    key="mission",
                    value=state.active_mission,
                    source="active_mission",
                    relevance=0.9,
                )

        if state.facts.get("event_type"):
            event_type = state.facts["event_type"]
            consolidated["last_event_type"] = event_type
            self.remember_semantic("last_event_type", event_type)

        if state.policy_result:
            self.remember_episodic(
                key="policy_result",
                value=state.policy_result,
                source="policy_manager",
                relevance=0.8,
            )

        if state.tool_evidence:
            self.remember_episodic(
                key="tool_evidence",
                value=state.tool_evidence,
                source="tool_engine",
                relevance=0.7,
            )

        return consolidated

    def relevant_for_state(self, state: CognitiveState) -> Dict[str, Any]:
        relevant = dict(self.semantic)

        if state.active_mission:
            mission_type = state.active_mission.get("type")
            if mission_type:
                relevant["current_mission_type"] = mission_type

        return relevant