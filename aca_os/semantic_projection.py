from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Mapping, Sequence
from uuid import uuid4

from aca_core.text import normalize_text
from aca_os.semantic_authority import SemanticRepresentation


SEMANTIC_PROJECTION_CONTRACT = "semantic_projection.v1"
SEMANTIC_PROJECTION_VERSION = 1
SEMANTIC_PROJECTION_COMPARISON_CONTRACT = "semantic_projection_comparison.v1"
PROJECTION_NAMES = (
    "conversational_act",
    "conversation_intent_model",
    "intent_projection",
    "entity_projection",
    "fact_projection",
    "slot_projection",
    "topic_projection",
    "goal_projection",
)
PROJECTION_STATUSES = ("MATCH", "DIFFERENT", "MISSING", "EXTRA")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(_freeze(item) for item in sorted(value, key=repr))
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _thaw(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SemanticProjection:
    """Immutable, passive contracts projected only from SemanticRepresentation."""

    projection_id: str
    representation_id: str
    version: int
    created_at: str
    conversational_act: Mapping[str, Any]
    conversation_intent_model: Mapping[str, Any]
    intent_projection: Mapping[str, Any]
    entity_projection: Mapping[str, Any]
    fact_projection: Mapping[str, Any]
    slot_projection: Mapping[str, Any]
    topic_projection: Mapping[str, Any]
    goal_projection: Mapping[str, Any]
    metadata: Mapping[str, Any]
    contract: str = SEMANTIC_PROJECTION_CONTRACT

    def __post_init__(self) -> None:
        for name in (*PROJECTION_NAMES, "metadata"):
            object.__setattr__(self, name, _freeze(getattr(self, name)))

    def projection_payload(self) -> dict[str, Any]:
        return {name: _thaw(getattr(self, name)) for name in PROJECTION_NAMES}

    @property
    def projection_hash(self) -> str:
        return _sha256(self.projection_payload())

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "projection_id": self.projection_id,
            "representation_id": self.representation_id,
            "version": self.version,
            "created_at": self.created_at,
            **self.projection_payload(),
            "metadata": _thaw(self.metadata),
            "projection_hash": self.projection_hash,
        }


class SemanticProjector:
    """Projects observable runtime contracts without reading legacy decisions."""

    component_name = "semantic_projector"
    mode = "shadow"
    version = "sa-2"

    def project(self, representation: SemanticRepresentation) -> SemanticProjection:
        source = representation.to_dict()
        segments = list(source.get("semantic_segments") or [])
        intents = _ordered(source.get("intents") or [])
        goals = _ordered(source.get("goals") or [])
        entities = list(source.get("entities") or [])
        assertions = list(source.get("assertions") or [])
        topics = list((source.get("topic_structure") or {}).get("topics") or [])

        conversational_act = _project_conversational_act(source)
        conversation_intent_model = _project_conversation_intent_model(
            segments=segments,
            intents=intents,
            goals=goals,
            constraints=source.get("constraints") or [],
            uncertainty=source.get("uncertainty") or [],
        )
        intent_projection = _project_intents(intents)
        entity_projection = _project_entities(entities)
        fact_projection = _project_facts(assertions, source.get("corrections") or [])
        slot_projection = _project_slots(
            assertions=assertions,
            uncertainty=source.get("uncertainty") or [],
            grounding=source.get("grounding") or {},
        )
        topic_projection = _project_topics(
            topics=topics,
            topic_structure=source.get("topic_structure") or {},
        )
        goal_projection = _project_goals(goals)

        created_at = utc_now_iso()
        return SemanticProjection(
            projection_id=str(uuid4()),
            representation_id=representation.representation_id,
            version=SEMANTIC_PROJECTION_VERSION,
            created_at=created_at,
            conversational_act=conversational_act,
            conversation_intent_model=conversation_intent_model,
            intent_projection=intent_projection,
            entity_projection=entity_projection,
            fact_projection=fact_projection,
            slot_projection=slot_projection,
            topic_projection=topic_projection,
            goal_projection=goal_projection,
            metadata={
                "component": self.component_name,
                "mode": self.mode,
                "projector_version": self.version,
                "source_contract": representation.contract,
                "source_projection_hash": representation.projection_hash,
                "decision_influence": False,
                "state_mutation": False,
                "created_at": created_at,
            },
        )


def _project_conversational_act(source: Mapping[str, Any]) -> dict[str, Any]:
    act = dict(source.get("conversational_act") or {})
    return {
        "contract": "conversational_act.v1",
        "act": str(act.get("act") or "unknown"),
        "confidence": float(act.get("confidence") or 0.0),
        "reason": "semantic_representation_projection",
        "evidence": dict(act.get("evidence") or {}),
        "target": _correction_target(source.get("corrections") or []),
        "impact": {
            "intent_override": False,
            "decision_influence": False,
        },
        "component": "semantic_projector",
        "turn": int((source.get("metadata") or {}).get("turn_number") or 0),
    }


def _project_conversation_intent_model(
    *,
    segments: Sequence[Mapping[str, Any]],
    intents: Sequence[Mapping[str, Any]],
    goals: Sequence[Mapping[str, Any]],
    constraints: Sequence[Mapping[str, Any]],
    uncertainty: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    selected_intent = dict(intents[0]) if intents else {}
    selected_goal = dict(goals[0]) if goals else {}
    explicit_questions = [
        {
            "id": f"explicit_question:{index}",
            "question": segment.get("text"),
            "confidence": 0.9,
            "evidence": {"segment_id": segment.get("segment_id")},
        }
        for index, segment in enumerate(segments, start=1)
        if segment.get("kind") == "question"
    ]
    missing_information = [
        {
            "key": item.get("type") or "uncertainty",
            "scope": item.get("scope"),
            "confidence": item.get("confidence", 0.0),
            "source": "semantic_representation.uncertainty",
            "evidence": dict(item.get("evidence") or {}),
        }
        for item in uncertainty
    ]
    dominant_key = str(selected_intent.get("type") or selected_goal.get("target") or "unknown")
    dominant_confidence = float(selected_intent.get("confidence") or selected_goal.get("confidence") or 0.0)
    dominant = {
        "key": dominant_key,
        "need_key": dominant_key,
        "label": dominant_key.replace("_", " "),
        "confidence": dominant_confidence,
        "source": "semantic_representation",
        "evidence": dict(selected_intent.get("evidence") or selected_goal.get("evidence") or {}),
    }
    user_goal = {
        "key": str(selected_goal.get("type") or dominant_key),
        "target": selected_goal.get("target") or dominant_key,
        "label": str(selected_goal.get("target") or dominant_key).replace("_", " "),
        "source": "semantic_representation.goals",
        "confidence": float(selected_goal.get("confidence") or dominant_confidence),
    }
    response_objective = {
        "key": str(selected_goal.get("type") or dominant_key),
        "need_key": dominant_key,
        "label": str(selected_goal.get("target") or dominant_key).replace("_", " "),
        "confidence": float(selected_goal.get("confidence") or dominant_confidence),
        "evidence": dict(selected_goal.get("evidence") or selected_intent.get("evidence") or {}),
    }
    return {
        "contract": "conversational_intent_model.v1",
        "explicit_questions": explicit_questions,
        "implicit_questions": [],
        "dominant_concern": dominant,
        "user_goal": user_goal,
        "user_assumptions": [
            {
                "key": item.get("type"),
                "value": item.get("value"),
                "confidence": item.get("confidence", 0.0),
                "evidence": dict(item.get("evidence") or {}),
            }
            for item in constraints
        ],
        "missing_information": missing_information,
        "response_objective": response_objective,
        "component": "semantic_projector",
        "decision_influence": False,
    }


def _project_intents(intents: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    candidates = [
        {
            "intent": item.get("type"),
            "confidence": float(item.get("confidence") or 0.0),
            "priority": int(item.get("priority") or 0),
            "explicit": bool(item.get("explicit")),
            "topic_id": item.get("topic_id"),
            "evidence": dict(item.get("evidence") or {}),
        }
        for item in intents
    ]
    selected = dict(candidates[0]) if candidates else {}
    return {
        "contract": "intent_projection.v1",
        "selected": selected,
        "candidates": candidates,
        "intent": selected.get("intent"),
        "confidence": selected.get("confidence", 0.0),
        "matched_terms": list((selected.get("evidence") or {}).get("matched_markers") or []),
        "reason": "semantic_representation_projection" if selected else "no_semantic_intent",
        "decision_influence": False,
    }


def _project_entities(entities: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    items = [
        {
            "entity_id": item.get("entity_id"),
            "type": item.get("type"),
            "value": item.get("value"),
            "role": item.get("role"),
            "confidence": float(item.get("confidence") or 0.0),
            "evidence": dict(item.get("evidence") or {}),
        }
        for item in entities
    ]
    return {
        "contract": "entity_projection.v1",
        "items": items,
        "count": len(items),
        "component": "semantic_projector",
    }


def _project_facts(
    assertions: Sequence[Mapping[str, Any]],
    corrections: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    corrections_by_target = {
        str(item.get("target")): item
        for item in corrections
        if item.get("target")
    }
    items = []
    for assertion in assertions:
        predicate = str(assertion.get("predicate") or "")
        if predicate in {"user_statement", "user_question"}:
            continue
        correction = corrections_by_target.get(predicate)
        items.append(
            {
                "fact_id": assertion.get("assertion_id"),
                "type": predicate,
                "value": assertion.get("value"),
                "status": "revision_proposed" if correction else "projected",
                "polarity": assertion.get("polarity"),
                "modality": assertion.get("modality"),
                "confidence": float(assertion.get("confidence") or 0.0),
                "evidence": dict(assertion.get("evidence") or {}),
            }
        )
    return {
        "contract": "fact_projection.v1",
        "items": items,
        "count": len(items),
        "corrections": [dict(item) for item in corrections],
        "component": "semantic_projector",
    }


def _project_slots(
    *,
    assertions: Sequence[Mapping[str, Any]],
    uncertainty: Sequence[Mapping[str, Any]],
    grounding: Mapping[str, Any],
) -> dict[str, Any]:
    slots: dict[str, dict[str, Any]] = {}
    for assertion in assertions:
        name = str(assertion.get("predicate") or "")
        if name in {"", "user_statement", "user_question"}:
            continue
        uncertain = assertion.get("modality") == "uncertain"
        slots[name] = {
            "name": name,
            "status": "partially_filled" if uncertain else "answered",
            "value": assertion.get("value"),
            "confidence": float(assertion.get("confidence") or 0.0),
            "evidence": dict(assertion.get("evidence") or {}),
            "source": "semantic_representation.assertions",
        }
    for reference in grounding.get("pending_question_references") or []:
        name = str(reference or "")
        if not name or name in slots:
            continue
        slots[name] = {
            "name": name,
            "status": "pending",
            "value": None,
            "confidence": 1.0,
            "evidence": {"grounding_reference": name},
            "source": "semantic_representation.grounding",
        }
    return {
        "contract": "slot_projection.v1",
        "items": list(slots.values()),
        "count": len(slots),
        "uncertainty": [dict(item) for item in uncertainty],
        "component": "semantic_projector",
    }


def _project_topics(
    *,
    topics: Sequence[Mapping[str, Any]],
    topic_structure: Mapping[str, Any],
) -> dict[str, Any]:
    primary_id = topic_structure.get("primary_topic")
    projected = []
    active_topic: dict[str, Any] = {}
    for topic in topics:
        item = {
            "id": topic.get("topic_id"),
            "type": topic.get("type"),
            "status": "active" if topic.get("topic_id") == primary_id else "observed",
            "priority": int(topic.get("priority") or 0),
            "confidence": float(topic.get("confidence") or 0.0),
            "segment_ids": list(topic.get("segment_ids") or []),
            "source": "semantic_representation.topic_structure",
        }
        projected.append(item)
        if item["status"] == "active":
            active_topic = dict(item)
    return {
        "contract": "topic_projection.v1",
        "topics": projected,
        "active_topic": active_topic,
        "multiple_topics": bool(topic_structure.get("multiple_topics")),
        "relationships": [dict(item) for item in topic_structure.get("relationships") or []],
        "component": "semantic_projector",
    }


def _project_goals(goals: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    items = [
        {
            "goal_id": item.get("goal_id"),
            "type": item.get("type"),
            "target": item.get("target"),
            "priority": int(item.get("priority") or 0),
            "confidence": float(item.get("confidence") or 0.0),
            "evidence": dict(item.get("evidence") or {}),
            "status": "projected",
        }
        for item in goals
    ]
    return {
        "contract": "goal_projection.v1",
        "goals": items,
        "primary_goal": dict(items[0]) if items else {},
        "count": len(items),
        "component": "semantic_projector",
    }


def _correction_target(corrections: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not corrections:
        return {}
    correction = corrections[0]
    return {
        "operation": correction.get("operation"),
        "target": correction.get("target"),
        "confidence": correction.get("confidence"),
    }


def _ordered(values: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    indexed = [(index, dict(value)) for index, value in enumerate(values)]
    indexed.sort(
        key=lambda item: (
            int(item[1].get("priority") or 999),
            -float(item[1].get("confidence") or 0.0),
            item[0],
        )
    )
    return [value for _, value in indexed]


def capture_legacy_projection(
    *,
    conversational_act: Mapping[str, Any] | None,
    conversation_intent_model: Mapping[str, Any] | None,
    intent_match: Mapping[str, Any] | None,
    entities: Mapping[str, Any] | None,
    fact_assimilation: Mapping[str, Any] | None,
    fact_revision: Mapping[str, Any] | None,
    slot_resolution: Mapping[str, Any] | None,
    slots: Mapping[str, Any] | None,
    topic_stack: Mapping[str, Any] | None,
    conversation_goal: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Capture legacy outputs as data; it never executes or copies legacy rules."""

    act = _unwrap_mapping(conversational_act, "selected")
    intent_model = _unwrap_mapping(conversation_intent_model, "model")
    legacy_intent = dict(intent_match or {})
    entity_items = _legacy_entities(entities or {})
    fact_items = _legacy_facts(fact_assimilation or {}, fact_revision or {})
    slot_items = _legacy_slots(slot_resolution or {}, slots or {}, fact_items)
    topics = _legacy_topics(topic_stack or {})
    goal = _unwrap_mapping(conversation_goal, "goal")
    goal_items = [goal] if goal else []
    captured_at = utc_now_iso()
    payload = {
        "contract": "legacy_semantic_projection_snapshot.v1",
        "captured_at": captured_at,
        "conversational_act": act,
        "conversation_intent_model": intent_model,
        "intent_projection": {
            "contract": "legacy_intent_projection.v1",
            "selected": legacy_intent,
            "candidates": [legacy_intent] if legacy_intent else [],
            "intent": legacy_intent.get("intent"),
            "confidence": legacy_intent.get("confidence", 0.0),
        },
        "entity_projection": {
            "contract": "legacy_entity_projection.v1",
            "items": entity_items,
            "count": len(entity_items),
        },
        "fact_projection": {
            "contract": "legacy_fact_projection.v1",
            "items": fact_items,
            "count": len(fact_items),
        },
        "slot_projection": {
            "contract": "legacy_slot_projection.v1",
            "items": slot_items,
            "count": len(slot_items),
        },
        "topic_projection": topics,
        "goal_projection": {
            "contract": "legacy_goal_projection.v1",
            "goals": goal_items,
            "primary_goal": goal,
            "count": len(goal_items),
        },
        "authority_mode": "legacy",
    }
    payload["projection_hash"] = _sha256(
        {name: payload.get(name, {}) for name in PROJECTION_NAMES}
    )
    return payload


def _unwrap_mapping(value: Mapping[str, Any] | None, key: str) -> dict[str, Any]:
    current = dict(value or {})
    nested = current.get(key)
    return dict(nested) if isinstance(nested, Mapping) else current


def _legacy_entities(entities: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "entity_id": f"legacy:{key}",
            "type": str(key),
            "role": str(key),
            "value": value,
            "confidence": 1.0,
            "source": "CognitiveState.entities",
        }
        for key, value in sorted(entities.items(), key=lambda item: str(item[0]))
    ]


def _legacy_facts(
    fact_assimilation: Mapping[str, Any],
    fact_revision: Mapping[str, Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()

    def append_fact(value: Any, *, source: str) -> None:
        if not isinstance(value, Mapping):
            return
        fact = dict(value)
        fact_type = str(fact.get("type") or fact.get("fact_type") or "")
        if not fact_type:
            return
        marker = f"{fact_type}:{_canonical_json(fact.get('value'))}:{fact.get('status')}"
        if marker in seen:
            return
        seen.add(marker)
        output.append(
            {
                "fact_id": fact.get("id") or f"legacy:{fact_type}:{len(output) + 1}",
                "type": fact_type,
                "value": fact.get("value"),
                "status": fact.get("status") or "active",
                "confidence": float(fact.get("confidence") or 0.0),
                "evidence": dict(fact.get("evidence") or {}),
                "source": source,
            }
        )

    for item in fact_assimilation.get("facts") or []:
        append_fact(item.get("fact") if isinstance(item, Mapping) else None, source="fact_assimilation")
    for key in ("confirmations", "redundant_facts"):
        for item in fact_assimilation.get(key) or []:
            if isinstance(item, Mapping):
                append_fact(item.get("fact") or item, source=f"fact_assimilation.{key}")
    for key in ("revisions", "withdrawals", "ambiguous_revisions"):
        for item in fact_revision.get(key) or []:
            if not isinstance(item, Mapping):
                continue
            append_fact(
                item.get("new_fact") or item.get("fact_after") or item.get("fact"),
                source=f"fact_revision.{key}",
            )
    return output


def _legacy_slots(
    slot_resolution: Mapping[str, Any],
    slots: Mapping[str, Any],
    fact_items: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for resolution in slot_resolution.get("resolutions") or []:
        if not isinstance(resolution, Mapping):
            continue
        value = resolution.get("slot_after") or resolution.get("slot") or {}
        if not isinstance(value, Mapping):
            continue
        item = dict(value)
        name = str(item.get("name") or resolution.get("slot") or "")
        if name:
            output[name] = {**item, "name": name, "source": "slot_resolution"}
    for fact in fact_items:
        name = str(fact.get("type") or "")
        if not name or name in output:
            continue
        slot = slots.get(name)
        if not isinstance(slot, Mapping):
            continue
        output[name] = {**dict(slot), "name": name, "source": "fact_assimilation"}
    return [output[key] for key in sorted(output)]


def _legacy_topics(topic_stack: Mapping[str, Any]) -> dict[str, Any]:
    topics = [dict(item) for item in topic_stack.get("topics") or [] if isinstance(item, Mapping)]
    active = topic_stack.get("active_topic")
    if not isinstance(active, Mapping):
        active = next(
            (item for item in topics if item.get("status") in {"active", "resumed"}),
            {},
        )
    return {
        "contract": "legacy_topic_projection.v1",
        "topics": topics,
        "active_topic": dict(active),
        "multiple_topics": len(topics) > 1,
    }


def compare_semantic_projection(
    legacy_projection: Mapping[str, Any],
    semantic_projection: SemanticProjection | Mapping[str, Any],
) -> dict[str, Any]:
    semantic = (
        semantic_projection.to_dict()
        if isinstance(semantic_projection, SemanticProjection)
        else _thaw(semantic_projection)
    )
    legacy = _thaw(legacy_projection)
    comparisons = {
        name: _compare_structure(
            name,
            legacy.get(name) or {},
            semantic.get(name) or {},
        )
        for name in PROJECTION_NAMES
    }
    metrics = _projection_metrics(legacy, semantic)
    status_counts = {
        status: sum(1 for item in comparisons.values() if item["status"] == status)
        for status in PROJECTION_STATUSES
    }
    overall_status = "MATCH" if status_counts["MATCH"] == len(PROJECTION_NAMES) else "DIFFERENT"
    field_diff = [
        {"projection": name, **field}
        for name, comparison in comparisons.items()
        for field in comparison["field_diff"]
        if field["status"] != "MATCH"
    ]
    missing_fields = [
        f"{name}.{field}"
        for name, comparison in comparisons.items()
        for field in comparison["missing_fields"]
    ]
    extra_fields = [
        f"{name}.{field}"
        for name, comparison in comparisons.items()
        for field in comparison["extra_fields"]
    ]
    payload = {
        "contract": SEMANTIC_PROJECTION_COMPARISON_CONTRACT,
        "authority_mode": "legacy",
        "semantic_authority_mode": "shadow",
        "overall_status": overall_status,
        "status_counts": status_counts,
        "legacy_projection": legacy,
        "semantic_projection": semantic,
        "projection_diff": comparisons,
        "field_diff": field_diff,
        "missing_fields": missing_fields,
        "extra_fields": extra_fields,
        "confidence": round(
            sum(float(item.get("confidence") or 0.0) for item in comparisons.values())
            / len(comparisons),
            4,
        ),
        "metrics": metrics,
        "decision_influence": False,
        "state_mutation": False,
        "compared_at": utc_now_iso(),
    }
    payload["projection_hash"] = _sha256(
        {
            "legacy_projection": legacy,
            "semantic_projection": semantic.get("projection_hash"),
            "projection_diff": comparisons,
            "metrics": metrics,
        }
    )
    return payload


def _compare_structure(
    name: str,
    legacy_projection: Mapping[str, Any],
    semantic_projection: Mapping[str, Any],
) -> dict[str, Any]:
    legacy = _canonical_projection(name, legacy_projection)
    semantic = _canonical_projection(name, semantic_projection)
    keys = sorted(set(legacy) | set(semantic))
    field_diff = []
    missing_fields = []
    extra_fields = []
    missing_values: dict[str, list[Any]] = {}
    extra_values: dict[str, list[Any]] = {}
    for key in keys:
        legacy_value = legacy.get(key)
        semantic_value = semantic.get(key)
        status = _field_status(legacy_value, semantic_value)
        if status == "MISSING":
            missing_fields.append(key)
        elif status == "EXTRA":
            extra_fields.append(key)
        if isinstance(legacy_value, list) and isinstance(semantic_value, list):
            missing = [item for item in legacy_value if item not in semantic_value]
            extra = [item for item in semantic_value if item not in legacy_value]
            if missing:
                missing_values[key] = missing
            if extra:
                extra_values[key] = extra
        field_diff.append(
            {
                "field": key,
                "status": status,
                "legacy": legacy_value,
                "semantic": semantic_value,
            }
        )
    statuses = {item["status"] for item in field_diff}
    if not field_diff or statuses == {"MATCH"}:
        status = "MATCH"
    elif _is_empty_projection(semantic) and not _is_empty_projection(legacy):
        status = "MISSING"
    elif _is_empty_projection(legacy) and not _is_empty_projection(semantic):
        status = "EXTRA"
    else:
        status = "DIFFERENT"
    return {
        "status": status,
        "legacy_projection": _thaw(legacy_projection),
        "semantic_projection": _thaw(semantic_projection),
        "projection_diff": {
            "matching_fields": [item["field"] for item in field_diff if item["status"] == "MATCH"],
            "different_fields": [item["field"] for item in field_diff if item["status"] == "DIFFERENT"],
            "missing_fields": list(missing_fields),
            "extra_fields": list(extra_fields),
            "missing_values": missing_values,
            "extra_values": extra_values,
        },
        "field_diff": field_diff,
        "missing_fields": missing_fields,
        "extra_fields": extra_fields,
        "confidence": _projection_confidence(semantic_projection, status=status),
    }


def _canonical_projection(name: str, value: Mapping[str, Any]) -> dict[str, Any]:
    if name == "conversational_act":
        return {
            "act": value.get("act"),
            "confidence": _rounded(value.get("confidence")),
        }
    if name == "conversation_intent_model":
        return {
            "explicit_questions": _question_values(value.get("explicit_questions") or []),
            "implicit_questions": _question_values(value.get("implicit_questions") or []),
            "dominant_concern": _semantic_key(value.get("dominant_concern")),
            "user_goal": _semantic_key(value.get("user_goal")),
            "missing_information": _semantic_keys(value.get("missing_information") or []),
            "response_objective": _semantic_key(value.get("response_objective")),
        }
    if name == "intent_projection":
        selected = value.get("selected") or value
        candidates = value.get("candidates") or ([selected] if selected else [])
        return {
            "selected": _intent_key(selected),
            "candidates": sorted({_intent_key(item) for item in candidates if _intent_key(item)}),
        }
    if name == "entity_projection":
        return {"items": sorted({_entity_key(item) for item in value.get("items") or []})}
    if name == "fact_projection":
        return {"items": sorted({_fact_key(item) for item in value.get("items") or []})}
    if name == "slot_projection":
        return {"items": sorted({_slot_key(item) for item in value.get("items") or []})}
    if name == "topic_projection":
        return {
            "topics": sorted({_topic_key(item) for item in value.get("topics") or []}),
            "active_topic": _topic_key(value.get("active_topic") or {}),
        }
    if name == "goal_projection":
        return {"goals": sorted({_goal_key(item) for item in value.get("goals") or []})}
    return _thaw(value)


def _field_status(legacy: Any, semantic: Any) -> str:
    if legacy == semantic:
        return "MATCH"
    if _is_empty(semantic) and not _is_empty(legacy):
        return "MISSING"
    if _is_empty(legacy) and not _is_empty(semantic):
        return "EXTRA"
    return "DIFFERENT"


def _is_empty_projection(value: Mapping[str, Any]) -> bool:
    return all(_is_empty(item) for item in value.values())


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {} or value == ()


def _rounded(value: Any) -> float:
    return round(float(value or 0.0), 3)


def _question_values(values: Sequence[Any]) -> list[str]:
    output = []
    for item in values:
        if isinstance(item, Mapping):
            value = item.get("question") or item.get("text") or item.get("key")
        else:
            value = item
        if value:
            output.append(normalize_text(value))
    return sorted(set(output))


def _semantic_key(value: Any) -> str:
    if not isinstance(value, Mapping):
        return normalize_text(value) if value else ""
    return normalize_text(
        value.get("key")
        or value.get("need_key")
        or value.get("target")
        or value.get("type")
        or value.get("label")
        or ""
    )


def _semantic_keys(values: Sequence[Any]) -> list[str]:
    return sorted({_semantic_key(item) for item in values if _semantic_key(item)})


def _intent_key(value: Any) -> str:
    if not isinstance(value, Mapping):
        return normalize_text(value) if value else ""
    return normalize_text(value.get("intent") or value.get("type") or "")


def _entity_key(value: Mapping[str, Any]) -> str:
    return "|".join(
        (
            normalize_text(value.get("type") or ""),
            normalize_text(value.get("role") or ""),
            _canonical_json(value.get("value")),
        )
    )


def _fact_key(value: Mapping[str, Any]) -> str:
    return f"{normalize_text(value.get('type') or value.get('predicate') or '')}|{_canonical_json(value.get('value'))}"


def _slot_key(value: Mapping[str, Any]) -> str:
    return f"{normalize_text(value.get('name') or value.get('slot') or '')}|{_canonical_json(value.get('value'))}"


def _topic_key(value: Mapping[str, Any]) -> str:
    return normalize_text(value.get("type") or value.get("id") or value.get("topic_id") or "")


def _goal_key(value: Mapping[str, Any]) -> str:
    return "|".join(
        (
            normalize_text(value.get("type") or value.get("act") or value.get("intention") or ""),
            normalize_text(value.get("target") or value.get("intention") or value.get("act") or ""),
        )
    ).strip("|")


def _projection_confidence(value: Mapping[str, Any], *, status: str) -> float:
    confidences: list[float] = []

    def visit(item: Any) -> None:
        if isinstance(item, Mapping):
            for key, child in item.items():
                if key == "confidence" and isinstance(child, (int, float)):
                    confidences.append(float(child))
                else:
                    visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    if confidences:
        return round(sum(confidences) / len(confidences), 4)
    return 1.0 if status == "MATCH" else 0.5


def _projection_metrics(
    legacy: Mapping[str, Any],
    semantic: Mapping[str, Any],
) -> dict[str, float]:
    legacy_entities = set(_canonical_projection("entity_projection", legacy.get("entity_projection") or {})["items"])
    semantic_entities = set(_canonical_projection("entity_projection", semantic.get("entity_projection") or {})["items"])
    legacy_facts = set(_canonical_projection("fact_projection", legacy.get("fact_projection") or {})["items"])
    semantic_facts = set(_canonical_projection("fact_projection", semantic.get("fact_projection") or {})["items"])
    legacy_slots = set(_canonical_projection("slot_projection", legacy.get("slot_projection") or {})["items"])
    semantic_slots = set(_canonical_projection("slot_projection", semantic.get("slot_projection") or {})["items"])
    legacy_topics = set(_canonical_projection("topic_projection", legacy.get("topic_projection") or {})["topics"])
    semantic_topics = set(_canonical_projection("topic_projection", semantic.get("topic_projection") or {})["topics"])
    legacy_goals = set(_canonical_projection("goal_projection", legacy.get("goal_projection") or {})["goals"])
    semantic_goals = set(_canonical_projection("goal_projection", semantic.get("goal_projection") or {})["goals"])
    legacy_intent = _canonical_projection("intent_projection", legacy.get("intent_projection") or {})["selected"]
    semantic_intent = _canonical_projection("intent_projection", semantic.get("intent_projection") or {})["selected"]
    return {
        "entity_recall": _recall(legacy_entities, semantic_entities),
        "entity_precision": _precision(legacy_entities, semantic_entities),
        "fact_recall": _recall(legacy_facts, semantic_facts),
        "fact_precision": _precision(legacy_facts, semantic_facts),
        "slot_recall": _recall(legacy_slots, semantic_slots),
        "slot_precision": _precision(legacy_slots, semantic_slots),
        "topic_agreement": _jaccard(legacy_topics, semantic_topics),
        "intent_agreement": 1.0 if legacy_intent == semantic_intent else 0.0,
        "goal_agreement": _jaccard(legacy_goals, semantic_goals),
    }


def _recall(expected: set[str], actual: set[str]) -> float:
    if not expected:
        return 1.0
    return round(len(expected & actual) / len(expected), 4)


def _precision(expected: set[str], actual: set[str]) -> float:
    if not actual:
        return 1.0 if not expected else 0.0
    return round(len(expected & actual) / len(actual), 4)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return round(len(left & right) / len(left | right), 4)


def semantic_projection_shadow_record(
    projection: SemanticProjection | None,
    comparison: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if projection is None:
        return {
            "contract": "semantic_projection_shadow.v1",
            "available": False,
            "authority_mode": "legacy",
            "semantic_authority_mode": "shadow",
        }
    projection_data = projection.to_dict()
    comparison_data = _thaw(comparison or {})
    return {
        "contract": "semantic_projection_shadow.v1",
        "available": True,
        "authority_mode": "legacy",
        "semantic_authority_mode": "shadow",
        "semantic_projection_id": projection.projection_id,
        "semantic_representation_id": projection.representation_id,
        "semantic_projection_version": projection.version,
        "semantic_projection_hash": projection.projection_hash,
        "semantic_projection": projection_data,
        "legacy_projection": comparison_data.get("legacy_projection", {}),
        "projection_diff": comparison_data.get("projection_diff", {}),
        "field_diff": comparison_data.get("field_diff", []),
        "missing_fields": comparison_data.get("missing_fields", []),
        "extra_fields": comparison_data.get("extra_fields", []),
        "confidence": comparison_data.get("confidence", 0.0),
        "metrics": comparison_data.get("metrics", {}),
        "comparison": comparison_data,
        "timestamps": {
            "projected_at": projection.created_at,
            "compared_at": comparison_data.get("compared_at"),
            "recorded_at": utc_now_iso(),
        },
        "decision_influence": False,
        "state_mutation": False,
    }
