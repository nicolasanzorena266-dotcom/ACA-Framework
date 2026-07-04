from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping


@dataclass(frozen=True)
class ExecutionFlow:
    """Deterministic runtime flow produced without LLMs.

    A flow is not an execution result. It is an auditable routing decision that
    tells the runtime which internal phases should be involved for a planned
    action.
    """

    flow: str
    steps: List[str]
    source_action: str
    payload: Dict[str, Any] = field(default_factory=dict)
    reason: str = "zero_cost_rule_route"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow": self.flow,
            "steps": list(self.steps),
            "source_action": self.source_action,
            "payload": dict(self.payload),
            "reason": self.reason,
        }


class FlowRouter:
    """Zero-cost action-to-flow router.

    No LLM. No embeddings. No paid API.

    The router receives an ActionPlan-like object and returns the explicit
    runtime flow that should handle it. This keeps execution routing separate
    from intent detection and action planning.
    """

    def __init__(self, routes: Mapping[str, Mapping[str, Any]] | None = None):
        self.routes: Dict[str, Dict[str, Any]] = {
            action: dict(route)
            for action, route in (routes or DEFAULT_FLOW_ROUTES).items()
        }

    def route(self, action_plan: Mapping[str, Any] | object) -> ExecutionFlow:
        data = _as_mapping(action_plan)
        action = str(data.get("action", "fallback_response"))
        action_payload = data.get("payload", {})
        if not isinstance(action_payload, Mapping):
            action_payload = {}

        route = self.routes.get(action)
        if not route:
            return ExecutionFlow(
                flow="fallback",
                steps=["kernel", "memory", "context", "output"],
                source_action=action,
                payload={"message_key": "fallback"},
                reason="no_flow_route_matched",
            )

        payload = dict(route.get("payload", {}))
        payload.update(dict(action_payload))

        return ExecutionFlow(
            flow=str(route["flow"]),
            steps=list(route["steps"]),
            source_action=action,
            payload=payload,
        )


def _as_mapping(value: Mapping[str, Any] | object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value

    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        mapped = to_dict()
        if isinstance(mapped, Mapping):
            return mapped

    return {}


DEFAULT_FLOW_ROUTES: Dict[str, Dict[str, Any]] = {
    "static_response": {
        "flow": "static_response",
        "steps": ["kernel", "memory", "context", "output"],
    },
    "process_guidance": {
        "flow": "guided_process",
        "steps": ["policy", "kernel", "memory", "context", "output"],
    },
    "knowledge_lookup": {
        "flow": "knowledge_lookup",
        "steps": ["policy", "tool_lookup", "kernel", "memory", "context", "output"],
    },
    "safe_escalation": {
        "flow": "safe_escalation",
        "steps": ["policy", "escalation", "memory", "context", "output"],
    },
    "human_handoff": {
        "flow": "human_handoff",
        "steps": ["policy", "handoff", "memory", "context", "output"],
    },
    "clarify": {
        "flow": "clarification",
        "steps": ["kernel", "memory", "context", "output"],
    },
    "fallback_response": {
        "flow": "fallback",
        "steps": ["kernel", "memory", "context", "output"],
    },
}
