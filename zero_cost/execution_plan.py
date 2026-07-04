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
class ExecutionPlan:
    """Serializable execution model produced from a routed flow.

    The plan is the formal runtime contract between routing and future
    execution. Sprint 23 keeps execution behavior unchanged while making the
    pipeline visible and auditable.
    """

    flow: str
    steps: List[ExecutionStep]
    source_action: str
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
            payload=dict(payload),
        )

    def step_names(self) -> List[str]:
        return [step.name for step in self.steps]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow": self.flow,
            "steps": [step.to_dict() for step in self.steps],
            "source_action": self.source_action,
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
