from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Sequence

ConfidenceLevel = Literal["low", "medium", "high"]
SignalLevel = Literal["none", "low", "medium", "high"]
RiskLevel = Literal["low", "medium", "high"]
Authorization = Literal["authorized", "blocked", "needs_clarification"]
NextAction = Literal["answer", "ask_clarification", "explain_limit", "prepare_handoff", "repair", "show_example"]


@dataclass(frozen=True)
class InteractionSignals:
    frustration: SignalLevel = "none"
    confusion: SignalLevel = "none"
    urgency: SignalLevel = "none"
    repetition: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "frustration": self.frustration,
            "confusion": self.confusion,
            "urgency": self.urgency,
            "repetition": self.repetition,
        }


@dataclass(frozen=True)
class SemanticParse:
    intent: str
    topic: str | None
    user_goal: str
    known_facts: tuple[str, ...] = ()
    missing_facts: tuple[str, ...] = ()
    signals: InteractionSignals = field(default_factory=InteractionSignals)
    confidence: float = 0.0
    requires_tool: bool = False
    risk_level: RiskLevel = "low"
    requested_action: str = "answer_with_guidance"
    entities: Mapping[str, Any] = field(default_factory=dict)
    refers_to_previous: bool = False

    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence >= 0.8:
            return "high"
        if self.confidence >= 0.65:
            return "medium"
        return "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "topic": self.topic,
            "user_goal": self.user_goal,
            "known_facts": list(self.known_facts),
            "missing_facts": list(self.missing_facts),
            "signals": self.signals.to_dict(),
            "confidence": round(float(self.confidence), 3),
            "requires_tool": bool(self.requires_tool),
            "risk_level": self.risk_level,
            "requested_action": self.requested_action,
            "entities": dict(self.entities),
            "refers_to_previous": bool(self.refers_to_previous),
        }


@dataclass(frozen=True)
class PolicyDecision:
    requested_action: str
    tool_required: str | None = None
    tool_available: bool = False
    authorization: Authorization = "authorized"
    fallback: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_action": self.requested_action,
            "tool_required": self.tool_required,
            "tool_available": self.tool_available,
            "authorization": self.authorization,
            "fallback": self.fallback,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class PlannerDecision:
    next_action: NextAction
    strategy: str
    needs_clarification: bool = False
    tool_request: str | None = None
    handoff_target: str | None = None
    must_include: tuple[str, ...] = ()
    must_not_include: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "next_action": self.next_action,
            "strategy": self.strategy,
            "needs_clarification": self.needs_clarification,
            "tool_request": self.tool_request,
            "handoff_target": self.handoff_target,
            "must_include": list(self.must_include),
            "must_not_include": list(self.must_not_include),
        }


@dataclass(frozen=True)
class SupervisorResult:
    passes: bool
    issues: tuple[str, ...] = ()
    requires_rewrite: bool = False
    blocked_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "passes": self.passes,
            "issues": list(self.issues),
            "requires_rewrite": self.requires_rewrite,
            "blocked_reason": self.blocked_reason,
        }


@dataclass(frozen=True)
class TraceBundle:
    public_trace: Mapping[str, Any]
    developer_trace: Mapping[str, Any]


def make_trace_id(conversation_id: str, turn_count: int, message: str) -> str:
    seed = f"{conversation_id}:{turn_count}:{message}".encode("utf-8")
    return "trace_" + hashlib.sha1(seed).hexdigest()[:12]


def now_ms() -> int:
    return int(time.time() * 1000)


def contains_any(text: str, terms: Sequence[str]) -> bool:
    return any(term in text for term in terms)
