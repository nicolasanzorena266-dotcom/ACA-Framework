from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from aca_kernel.core.state import CognitiveState
from aca_os.conversation_state import ConversationState
from zero_cost.execution_plan import ExecutionPlan


CONVERSATION_OBJECTIVE_CONTRACT = "conversation_objective.v1"
CONVERSATION_FIRST_MODE = "conversation_objective"
LEGACY_RESPONSE_MODE = "legacy_response"

_NEXT_STEP_ACTIONS = {
    "converse",
    "respond",
    "request_information",
    "execute_tool",
    "consult_knowledge",
    "handoff",
    "finish",
}


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _mapping(value: Any) -> dict[str, Any]:
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _trace_payload(value: Any, payload_key: str) -> dict[str, Any]:
    mapped = _mapping(value)
    payload = mapped.get(payload_key)
    return _mapping(payload) if isinstance(payload, Mapping) else mapped


@dataclass(frozen=True)
class ConversationObjective:
    """Language-free description of what ACA must accomplish in the turn."""

    goal: Mapping[str, Any]
    missing_information: tuple[str, ...]
    next_step: Mapping[str, Any]
    empathy: str
    tone: str
    urgency: str
    constraints: tuple[str, ...]
    conversation_mode: str = "natural"
    emoji: str = "allowed"
    contract: str = CONVERSATION_OBJECTIVE_CONTRACT

    def __post_init__(self) -> None:
        object.__setattr__(self, "goal", _freeze(self.goal))
        object.__setattr__(self, "missing_information", tuple(str(item) for item in self.missing_information))
        object.__setattr__(self, "next_step", _freeze(self.next_step))
        object.__setattr__(self, "constraints", tuple(str(item) for item in self.constraints))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "goal": _thaw(self.goal),
            "missing_information": list(self.missing_information),
            "next_step": _thaw(self.next_step),
            "empathy": self.empathy,
            "tone": self.tone,
            "urgency": self.urgency,
            "constraints": list(self.constraints),
            "conversation_mode": self.conversation_mode,
            "emoji": self.emoji,
        }

    @property
    def valid(self) -> bool:
        goal_type = str(self.goal.get("type") or "").strip()
        action = str(self.next_step.get("action") or "").strip()
        return bool(goal_type) and action in _NEXT_STEP_ACTIONS

    @property
    def projection_hash(self) -> str:
        encoded = json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConversationalFirstConfig:
    """Deployment switch for the reversible output-authority migration."""

    enabled: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ConversationalFirstConfig":
        source = os.environ if env is None else env
        raw = source.get("ACA_CONVERSATIONAL_FIRST_ENABLED")
        return cls(enabled=str(raw or "").strip().lower() in {"1", "true", "yes", "on"})


class ConversationObjectiveProjector:
    """Projects an output objective without interpreting the user message."""

    component_name = "conversation_objective_projector"

    def project(
        self,
        *,
        state: CognitiveState,
        execution_plan: ExecutionPlan,
        conversation_state: ConversationState | None,
        semantic_representation: Mapping[str, Any] | None = None,
        semantic_projection: Mapping[str, Any] | None = None,
    ) -> ConversationObjective:
        facts = state.facts if isinstance(state.facts, Mapping) else {}
        response_plan = _trace_payload(facts.get("conversation_response_plan"), "plan")
        conversation_plan = _trace_payload(facts.get("conversation_plan"), "plan")
        conversation_goal = _trace_payload(facts.get("conversation_goal"), "goal")
        semantic = _mapping(semantic_representation)
        projection = _mapping(semantic_projection)

        goal = _goal_projection(
            facts=facts,
            conversation_goal=conversation_goal,
            response_plan=response_plan,
            semantic_representation=semantic,
            semantic_projection=projection,
        )
        missing_information = _missing_information(
            response_plan=response_plan,
            conversation_state=conversation_state,
            goal=goal,
        )
        next_step = _next_step_projection(
            execution_plan=execution_plan,
            response_plan=response_plan,
            conversation_plan=conversation_plan,
            candidate_work=_candidate_work(facts),
            missing_information=missing_information,
            goal=goal,
        )
        urgency = _urgency(conversation_state, facts)
        empathy = _empathy(response_plan, urgency)
        constraints = _constraints(state, facts, semantic)
        return ConversationObjective(
            goal=goal,
            missing_information=missing_information,
            next_step=next_step,
            empathy=empathy,
            tone="friendly_professional",
            urgency=urgency,
            constraints=constraints,
            conversation_mode="natural",
            emoji="allowed" if urgency != "critical" else "disabled",
        )


class ObjectiveDeterministicRealizer:
    """Provider-independent, domain-neutral emergency realization."""

    def realize(self, objective: ConversationObjective) -> str:
        goal_type = str(objective.goal.get("type") or "")
        action = str(objective.next_step.get("action") or "converse")
        if goal_type in {"greet", "satisfy_intent:greet", "respond_to_greeting"}:
            return "Hola. ¿En qué puedo ayudarte?"
        if goal_type in {"acknowledge_thanks", "respond_to_thanks", "thank"}:
            return "De nada. Estoy acá para ayudarte."
        if action == "request_information":
            if objective.missing_information:
                field = _humanize_identifier(objective.missing_information[0])
                return f"Para poder seguir, ¿podés confirmarme {field}?"
            return "Para poder seguir, necesito que me confirmes un dato."
        if action == "execute_tool":
            return "Ya está todo listo para realizar la gestión indicada."
        if action == "consult_knowledge":
            return "Voy a darte la información disponible para resolver esta consulta."
        if action == "handoff":
            return "Este caso necesita continuar con el equipo correspondiente."
        if action == "finish":
            return "Listo. La gestión de este punto quedó completa."
        if action == "respond":
            return "Entiendo. Voy a responder directamente a lo que planteaste."
        return "Entiendo. Sigamos con lo que necesitás resolver."


def semantic_context_summary(
    representation: Mapping[str, Any] | None,
    projection: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return only authorized semantic evidence needed by language realization."""

    semantic = _mapping(representation)
    projected = _mapping(projection)
    allowed_semantic = (
        "language",
        "semantic_segments",
        "entities",
        "events",
        "assertions",
        "conversational_act",
        "intents",
        "goals",
        "constraints",
        "uncertainty",
        "corrections",
        "contradictions",
        "topic_structure",
    )
    summary = {key: deepcopy(semantic.get(key)) for key in allowed_semantic if key in semantic}
    if projected:
        summary["projection"] = {
            key: deepcopy(projected.get(key))
            for key in (
                "conversational_act",
                "intent_projection",
                "entity_projection",
                "fact_projection",
                "topic_projection",
                "goal_projection",
            )
            if key in projected
        }
    return summary


def conversation_context_summary(conversation_state: ConversationState | None) -> dict[str, Any]:
    if conversation_state is None:
        return {}
    active_topic = next(
        (
            deepcopy(dict(topic))
            for topic in conversation_state.topic_stack
            if str(topic.get("status") or "") in {"active", "resumed"}
        ),
        {},
    )
    return {
        "turn_count": int(conversation_state.turn_count),
        "active_mission": _structured_subset(
            conversation_state.active_mission or {},
            ("type", "status", "lifecycle_status", "progress", "next_act", "blockers", "missing"),
        ),
        "active_topic": _structured_subset(
            active_topic,
            ("id", "type", "mission_type", "priority", "status", "summary"),
        ),
        "confirmed_fact_keys": sorted(
            key
            for key in (conversation_state.confirmed_facts or {})
            if key not in {"last_event_type", "last_raw_payload"}
        )[:20],
    }


def _goal_projection(
    *,
    facts: Mapping[str, Any],
    conversation_goal: Mapping[str, Any],
    response_plan: Mapping[str, Any],
    semantic_representation: Mapping[str, Any],
    semantic_projection: Mapping[str, Any],
) -> dict[str, Any]:
    authority = _mapping(_mapping(facts.get("conversation_goal")).get("authority"))
    semantic_goal = _mapping(authority.get("semantic_primary_goal"))
    if not semantic_goal:
        projected_goal = _mapping(semantic_projection.get("goal_projection"))
        semantic_goal = _mapping(next(iter(projected_goal.get("goals") or []), {}))
    if not semantic_goal:
        semantic_goal = _mapping(next(iter(semantic_representation.get("goals") or []), {}))
    if semantic_goal:
        goal_type = str(semantic_goal.get("type") or "satisfy_user_need")
        target = str(semantic_goal.get("target") or "").strip()
        if target and _is_symbolic_identifier(target):
            goal_type = f"{goal_type}:{target}"
        return {
            "type": goal_type,
            "priority": _bounded_priority(semantic_goal.get("priority")),
            "confidence": _bounded_confidence(semantic_goal.get("confidence")),
            "source": "semantic_authority",
        }

    intention = str(conversation_goal.get("intention") or "").strip()
    if intention:
        return {
            "type": intention,
            "priority": _bounded_priority(conversation_goal.get("priority")),
            "confidence": _bounded_confidence(
                _mapping(conversation_goal.get("originating_act")).get("confidence")
            ),
            "source": "conversational_goal",
        }

    primary = _mapping(response_plan.get("primary_user_need"))
    return {
        "type": str(primary.get("key") or "satisfy_user_need"),
        "priority": 1,
        "confidence": _bounded_confidence(primary.get("confidence")),
        "source": "conversation_response_plan",
    }


def _missing_information(
    *,
    response_plan: Mapping[str, Any],
    conversation_state: ConversationState | None,
    goal: Mapping[str, Any],
) -> tuple[str, ...]:
    keys: list[str] = []
    for item in response_plan.get("required_information") or []:
        mapped = _mapping(item)
        key = str(mapped.get("slot") or mapped.get("key") or "").strip()
        if key and key not in keys:
            keys.append(key)

    explicit_goal = goal.get("source") == "semantic_authority" and float(goal.get("confidence") or 0.0) >= 0.8
    if explicit_goal:
        keys = [key for key in keys if key != "user_need"]

    if conversation_state is not None:
        pending = {
            str(name)
            for name, slot in (conversation_state.slots or {}).items()
            if isinstance(slot, Mapping)
            and str(slot.get("status") or "") in {"pending", "partially_filled"}
        }
        keys = [key for key in keys if key in pending or key not in conversation_state.slots]
    return tuple(keys[:3])


def _next_step_projection(
    *,
    execution_plan: ExecutionPlan,
    response_plan: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
    candidate_work: Mapping[str, Any],
    missing_information: Sequence[str],
    goal: Mapping[str, Any],
) -> dict[str, Any]:
    if missing_information:
        return {
            "action": "request_information",
            "target": str(missing_information[0]),
            "operation": None,
            "question_budget": 1,
        }

    operation = str(candidate_work.get("operation") or "").strip() or None
    source_action = str(execution_plan.source_action or "").strip()
    flow = str(execution_plan.flow or "").strip()
    if source_action in {"human_handoff", "escalate"} or flow in {"human_handoff", "safe_escalation"}:
        action = "handoff"
    elif operation or any(step.name == "tool_lookup" for step in execution_plan.steps):
        action = "execute_tool" if operation else "consult_knowledge"
    elif source_action in {"static_response", "answer", "respond"}:
        action = "respond"
    elif str(goal.get("type") or "").startswith("satisfy_intent:greet"):
        action = "converse"
    else:
        current_step = _mapping(_mapping(conversation_plan.get("active_plan")).get("current_step"))
        step_type = str(current_step.get("type") or "")
        action = "finish" if step_type == "completion" else "converse"
    response_next = _mapping(response_plan.get("next_action"))
    return {
        "action": action,
        "target": str(response_next.get("type") or source_action or "user_need"),
        "operation": operation,
        "question_budget": (
            1
            if str(goal.get("type") or "").startswith("satisfy_intent:greet")
            else 0
        ),
    }


def _candidate_work(facts: Mapping[str, Any]) -> dict[str, Any]:
    direct = _mapping(facts.get("candidate_work"))
    if direct:
        return direct
    operational = _mapping(facts.get("operational_work"))
    if operational.get("authoritative") is True and operational.get("mode") != "shadow":
        return _mapping(operational.get("selected_work"))
    return {}


def _urgency(conversation_state: ConversationState | None, facts: Mapping[str, Any]) -> str:
    mission = _mapping(conversation_state.active_mission if conversation_state else {})
    if any(str(item).lower() in {"safety", "injuries", "critical"} for item in mission.get("blockers") or []):
        return "critical"
    governance = _mapping(facts.get("operational_governance") or facts.get("operational_governance_assessment"))
    risk = str(governance.get("risk_level") or "").lower()
    if risk in {"high", "critical", "level_4"}:
        return "high"
    return "normal"


def _empathy(response_plan: Mapping[str, Any], urgency: str) -> str:
    concern = _mapping(response_plan.get("dominant_concern"))
    confidence = float(concern.get("confidence") or 0.0)
    if urgency in {"critical", "high"}:
        return "high"
    return "medium" if confidence >= 0.65 else "light"


def _constraints(
    state: CognitiveState,
    facts: Mapping[str, Any],
    semantic_representation: Mapping[str, Any],
) -> tuple[str, ...]:
    constraints = [
        "no_unverified_facts",
        "no_unapproved_operations",
        "no_unexecuted_tool_claims",
        "respect_policy",
        "preserve_cognitive_opacity",
    ]
    policy = _mapping(state.policy_result)
    if str(policy.get("decision") or "").upper() == "ESCALATE":
        constraints.append("handoff_required")
    for item in semantic_representation.get("constraints") or []:
        mapped = _mapping(item)
        constraint_type = str(mapped.get("type") or mapped.get("constraint") or "").strip()
        if constraint_type and _is_symbolic_identifier(constraint_type):
            constraints.append(constraint_type)
    governance = _mapping(facts.get("operational_governance") or facts.get("operational_governance_assessment"))
    if governance.get("requires_confirmation"):
        constraints.append("confirmation_required")
    if governance.get("requires_human_approval"):
        constraints.append("human_approval_required")
    return tuple(dict.fromkeys(constraints))


def _structured_subset(value: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    mapped = _mapping(value)
    return {key: deepcopy(mapped.get(key)) for key in keys if key in mapped}


def _is_symbolic_identifier(value: str) -> bool:
    return bool(value) and all(character.isalnum() or character in {"_", "-", ":"} for character in value)


def _bounded_priority(value: Any) -> int:
    try:
        return max(1, min(int(value), 100))
    except (TypeError, ValueError):
        return 1


def _bounded_confidence(value: Any) -> float:
    try:
        return round(max(0.0, min(float(value), 1.0)), 4)
    except (TypeError, ValueError):
        return 0.0


def _humanize_identifier(value: str) -> str:
    return str(value or "dato necesario").replace(":", " ").replace("_", " ").strip()
