from dataclasses import dataclass
from typing import Any, Dict, List

from aca_kernel.core.state import CognitiveState
from aca_os.memory_store import MemoryStore


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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryRecord":
        return cls(
            key=data["key"],
            value=data.get("value"),
            source=data.get("source", "unknown"),
            relevance=float(data.get("relevance", 1.0)),
        )


class MemoryEngine:
    """ACA OS memory system.

    Working memory lives during the active mission.
    Episodic memory stores relevant events.
    Semantic memory stores stable reusable knowledge.
    Procedural memory stores reusable resolution patterns.
    """

    def __init__(self, store: MemoryStore | None = None):
        self.store = store
        self.working: Dict[str, Any] = {}
        self.episodic: List[MemoryRecord] = []
        self.semantic: Dict[str, Any] = {}
        self.procedural: Dict[str, Any] = {}

        if self.store:
            self.load()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "working": self.working,
            "episodic": [record.to_dict() for record in self.episodic],
            "semantic": self.semantic,
            "procedural": self.procedural,
        }

    def load(self) -> None:
        if not self.store:
            return

        data = self.store.load()
        self.working = dict(data.get("working", {}))
        self.episodic = [
            MemoryRecord.from_dict(record)
            for record in data.get("episodic", [])
        ]
        self.semantic = dict(data.get("semantic", {}))
        self.procedural = dict(data.get("procedural", {}))

    def persist(self) -> None:
        if self.store:
            self.store.save(self.to_dict())

    def remember_working(self, key: str, value: Any) -> None:
        self.working[key] = value
        self.persist()

    def remember_semantic(self, key: str, value: Any) -> None:
        self.semantic[key] = value
        self.persist()

    def remember_episodic(self, key: str, value: Any, source: str, relevance: float = 1.0) -> None:
        self.episodic.append(
            MemoryRecord(
                key=key,
                value=value,
                source=source,
                relevance=relevance,
            )
        )
        self.persist()

    def clear_working(self) -> None:
        self.working.clear()
        self.persist()

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

        self.persist()
        return consolidated

    def relevant_for_state(self, state: CognitiveState) -> Dict[str, Any]:
        relevant = dict(self.semantic)

        if state.active_mission:
            mission_type = state.active_mission.get("type")
            if mission_type:
                relevant["current_mission_type"] = mission_type

        return relevant