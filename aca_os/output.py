from dataclasses import dataclass, field
from typing import Any, Dict, List

from aca_kernel.core.state import CognitiveState
from aca_os.event_bus import RuntimeEvent
from aca_os.execution_trace import ExecutionTrace
from aca_os.runtime_timeline import RuntimeTimeline


@dataclass(frozen=True)
class ACAOutput:
    conversation_id: str
    response: str | None
    selected_program: str | None
    mission: Dict[str, Any] | None
    intent_match: Dict[str, Any] | None
    policy_result: Dict[str, Any] | None
    tool_evidence: Dict[str, Any] = field(default_factory=dict)
    context_bundle: Dict[str, Any] | None = None
    trace: List[Dict[str, Any]] = field(default_factory=list)
    runtime_timeline: Dict[str, Any] = field(default_factory=dict)
    execution_trace: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_state(
        cls,
        state: CognitiveState,
        runtime_events: List[RuntimeEvent] | None = None,
        execution_trace: ExecutionTrace | None = None,
    ) -> "ACAOutput":
        return cls(
            conversation_id=state.conversation_id,
            response=state.response,
            selected_program=state.selected_program,
            mission=state.active_mission,
            intent_match=state.intent_match,
            policy_result=state.policy_result,
            tool_evidence=state.tool_evidence,
            context_bundle=state.context_bundle,
            trace=list(state.timeline),
            runtime_timeline=RuntimeTimeline.from_state(state, runtime_events).to_dict(),
            execution_trace=execution_trace.to_dict() if execution_trace else {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "response": self.response,
            "selected_program": self.selected_program,
            "mission": self.mission,
            "intent_match": self.intent_match,
            "policy_result": self.policy_result,
            "tool_evidence": self.tool_evidence,
            "context_bundle": self.context_bundle,
            "trace": self.trace,
            "runtime_timeline": self.runtime_timeline,
            "execution_trace": self.execution_trace,
        }