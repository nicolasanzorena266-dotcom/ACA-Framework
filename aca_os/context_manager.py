from dataclasses import dataclass, field
from typing import Any, Dict, List

from aca_kernel.core.state import CognitiveState


@dataclass(frozen=True)
class ContextBundle:
    mission: Dict[str, Any] | None = None
    facts: Dict[str, Any] = field(default_factory=dict)
    hypotheses: Dict[str, float] = field(default_factory=dict)
    plan: List[str] = field(default_factory=list)
    relevant_memory: Dict[str, Any] = field(default_factory=dict)
    tool_evidence: Dict[str, Any] = field(default_factory=dict)
    domain_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission": self.mission,
            "facts": self.facts,
            "hypotheses": self.hypotheses,
            "plan": self.plan,
            "relevant_memory": self.relevant_memory,
            "tool_evidence": self.tool_evidence,
            "domain_context": self.domain_context,
        }

    def to_conversation_state(self, *, conversation_id: str = "derived-context", turn_count: int = 0):
        from aca_os.conversation_state import ConversationState

        return ConversationState.from_context_bundle(
            self.to_dict(),
            conversation_id=conversation_id,
            turn_count=turn_count,
        )


class ContextManager:
    def build(
        self,
        state: CognitiveState,
        memory: Dict[str, Any] | None = None,
        tool_evidence: Dict[str, Any] | None = None,
        domain_context: Dict[str, Any] | None = None,
    ) -> ContextBundle:
        return ContextBundle(
            mission=state.active_mission,
            facts=dict(state.facts),
            hypotheses=dict(state.hypotheses),
            plan=list(state.plan),
            relevant_memory=memory or {},
            tool_evidence=tool_evidence or {},
            domain_context=domain_context or {},
        )
