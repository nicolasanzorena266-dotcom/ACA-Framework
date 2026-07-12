from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping


@dataclass(frozen=True)
class ExecutionStep:
    """Single deterministic step inside an ACA execution plan.

    A step is declarative. It does not execute anything by itself. The runtime
    can inspect, serialize, test, and later delegate these steps to an executor
    without depending on an LLM or an external service.
    """

    name: str
    required: bool = True
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "required": self.required,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class ExecutionStepOutcome:
    """Observable result produced for a planned execution step.

    Outcomes are cognitive execution records, not debug logs. They make the
    manual runtime path auditable today and provide the contract a future
    RuntimeExecutor can implement directly.
    """

    step: str
    executor: str
    status: str
    started_at: str
    finished_at: str
    duration_ms: float = 0.0
    result: Dict[str, Any] = field(default_factory=dict)
    evidence: Dict[str, Any] = field(default_factory=dict)
    state_changes: Dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    interruption: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "executor": self.executor,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "result": dict(self.result),
            "evidence": dict(self.evidence),
            "state_changes": dict(self.state_changes),
            "error": self.error,
            "interruption": dict(self.interruption or {}),
        }


@dataclass(frozen=True)
class ExecutionPlan:
    """Serializable execution model produced from a routed flow.

    The plan is the formal runtime contract between routing and execution. It
    names the flow selected by the runtime and the kernel program authorized to
    execute that flow.
    """

    flow: str
    steps: List[ExecutionStep]
    source_action: str
    kernel_program: str
    payload: Dict[str, Any] = field(default_factory=dict)
    reason: str = "zero_cost_execution_plan"

    @classmethod
    def from_flow(cls, execution_flow: Mapping[str, Any] | object) -> "ExecutionPlan":
        data = _as_mapping(execution_flow)
        flow = str(data.get("flow", "fallback"))
        source_action = str(data.get("source_action", "fallback_response"))
        payload = data.get("payload", {})
        if not isinstance(payload, Mapping):
            payload = {}

        raw_steps = data.get("steps", [])
        steps = [_build_step(step, payload=dict(payload)) for step in _as_iterable(raw_steps)]

        if not steps:
            steps = [ExecutionStep(name="output")]

        return cls(
            flow=flow,
            steps=steps,
            source_action=source_action,
            kernel_program=_kernel_program_for(flow, source_action, dict(payload)),
            payload=dict(payload),
        )

    def step_names(self) -> List[str]:
        return [step.name for step in self.steps]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow": self.flow,
            "steps": [step.to_dict() for step in self.steps],
            "source_action": self.source_action,
            "kernel_program": self.kernel_program,
            "payload": dict(self.payload),
            "reason": self.reason,
        }


def _build_step(value: Any, payload: Dict[str, Any]) -> ExecutionStep:
    if isinstance(value, ExecutionStep):
        return value

    if isinstance(value, Mapping):
        name = str(value.get("name", "unknown"))
        required = bool(value.get("required", True))
        step_payload = value.get("payload", {})
        if not isinstance(step_payload, Mapping):
            step_payload = {}
        return ExecutionStep(name=name, required=required, payload=dict(step_payload))

    name = str(value)
    step_payload = _payload_for_step(name, payload)
    return ExecutionStep(name=name, payload=step_payload)


def _payload_for_step(step_name: str, flow_payload: Dict[str, Any]) -> Dict[str, Any]:
    if step_name == "tool_lookup" and "tool_key" in flow_payload:
        return {"tool_key": flow_payload["tool_key"]}
    if step_name in {"escalation", "handoff"} and "reason" in flow_payload:
        return {"reason": flow_payload["reason"]}
    if step_name == "output" and "message_key" in flow_payload:
        return {"message_key": flow_payload["message_key"]}
    return {}


def _kernel_program_for(flow: str, source_action: str, payload: Dict[str, Any]) -> str:
    if flow == "knowledge_lookup":
        return "knowledge_lookup"
    if flow == "guided_process":
        return "auto_claim_guidance"
    if flow == "static_response" and payload.get("message_key") == "greeting":
        return "greeting"
    if flow in {"fallback", "clarification"}:
        return "fallback"
    if source_action == "fallback_response":
        return "fallback"
    return "fallback"


def _as_mapping(value: Mapping[str, Any] | object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        mapped = to_dict()
        if isinstance(mapped, Mapping):
            return mapped

    return {}


def _as_iterable(value: Any) -> Iterable[Any]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return value
    return []
