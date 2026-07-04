from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class ActionPlan:
    """Deterministic execution directive produced without LLMs."""

    action: str
    confidence: float
    source_intent: str
    payload: Dict[str, Any] = field(default_factory=dict)
    reason: str = "zero_cost_rule_plan"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "source_intent": self.source_intent,
            "payload": dict(self.payload),
            "reason": self.reason,
        }


class ActionPlanner:
    """Zero-cost intent-to-action planner.

    No LLM. No embeddings. No paid API.

    This component converts an intent match into a stable action plan. It does
    not execute tools and does not mutate state directly; the runtime records
    the resulting plan as auditable cognitive state.
    """

    def __init__(self, rules: Mapping[str, Mapping[str, Any]] | None = None):
        self.rules: Dict[str, Dict[str, Any]] = {
            intent: dict(rule)
            for intent, rule in (rules or DEFAULT_ACTION_RULES).items()
        }

    def plan(self, intent_match: Mapping[str, Any] | object) -> ActionPlan:
        data = _as_mapping(intent_match)
        intent = str(data.get("intent", "fallback"))
        confidence = float(data.get("confidence", 0.0) or 0.0)

        rule = self.rules.get(intent)
        if not rule:
            return ActionPlan(
                action="fallback_response",
                confidence=0.0,
                source_intent=intent,
                payload={"message_key": "fallback"},
                reason="no_action_rule_matched",
            )

        min_confidence = float(rule.get("min_confidence", 0.0))
        if confidence < min_confidence:
            return ActionPlan(
                action="clarify",
                confidence=confidence,
                source_intent=intent,
                payload={
                    "message_key": "clarify_low_confidence",
                    "required_confidence": min_confidence,
                },
                reason="below_min_confidence",
            )

        return ActionPlan(
            action=str(rule["action"]),
            confidence=confidence,
            source_intent=intent,
            payload=dict(rule.get("payload", {})),
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


DEFAULT_ACTION_RULES: Dict[str, Dict[str, Any]] = {
    "greeting": {
        "action": "static_response",
        "payload": {"message_key": "greeting"},
    },
    "auto_claim_guidance": {
        "action": "process_guidance",
        "min_confidence": 0.25,
        "payload": {"flow": "galicia_auto_claim_guidance"},
    },
    "concept_cleas": {
        "action": "knowledge_lookup",
        "payload": {"tool_key": "cleas"},
    },
    "concept_franquicia": {
        "action": "knowledge_lookup",
        "payload": {"tool_key": "franquicia"},
    },
    "concept_denuncia_administrativa": {
        "action": "knowledge_lookup",
        "payload": {"tool_key": "denuncia_administrativa"},
    },
    "real_claim_status": {
        "action": "safe_escalation",
        "payload": {"reason": "requires_real_claim_data"},
    },
    "human_request": {
        "action": "human_handoff",
        "payload": {"reason": "explicit_human_request"},
    },
    "fallback": {
        "action": "fallback_response",
        "payload": {"message_key": "fallback"},
    },
}
