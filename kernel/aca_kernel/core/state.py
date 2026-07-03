from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4
from copy import deepcopy

@dataclass(frozen=True)
class CognitiveState:
    conversation_id: str = field(default_factory=lambda: str(uuid4()))
    version: int = 1
    facts: Dict[str, Any] = field(default_factory=dict)
    entities: Dict[str, Any] = field(default_factory=dict)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    hypotheses: Dict[str, float] = field(default_factory=dict)
    scores: Dict[str, float] = field(default_factory=dict)
    goal: Optional[str] = None
    plan: List[str] = field(default_factory=list)
    response: Optional[str] = None
    selected_program: Optional[str] = None
    active_mission: Optional[Dict[str, Any]] = None
    policy_result: Optional[Dict[str, Any]] = None
    tool_evidence: Dict[str, Any] = field(default_factory=dict)
    memory_snapshot: Optional[Dict[str, Any]] = None
    context_bundle: Optional[Dict[str, Any]] = None
    compliance: List[Dict[str, Any]] = field(default_factory=list)
    timeline: List[Dict[str, Any]] = field(default_factory=list)

    def evolve(self, operation: str, **changes: Any) -> "CognitiveState":
        data = self.to_dict()
        data.update(deepcopy(changes))
        data["version"] = self.version + 1
        timeline = list(self.timeline)
        timeline.append({
            "from_version": self.version,
            "to_version": self.version + 1,
            "operation": operation,
            "changes": changes,
        })
        data["timeline"] = timeline
        return CognitiveState(**data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "version": self.version,
            "facts": deepcopy(self.facts),
            "entities": deepcopy(self.entities),
            "relations": deepcopy(self.relations),
            "hypotheses": deepcopy(self.hypotheses),
            "scores": deepcopy(self.scores),
            "goal": self.goal,
            "plan": deepcopy(self.plan),
            "response": self.response,
            "selected_program": self.selected_program,
            "active_mission": deepcopy(self.active_mission),
            "policy_result": deepcopy(self.policy_result),
            "tool_evidence": deepcopy(self.tool_evidence),
            "memory_snapshot": deepcopy(self.memory_snapshot),
            "context_bundle": deepcopy(self.context_bundle),
            "compliance": deepcopy(self.compliance),
            "timeline": deepcopy(self.timeline),
        }