from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from copy import deepcopy
from typing import Any, Mapping, Sequence

from aca_os.semantic_projection import compare_semantic_projection


SEMANTIC_AUTHORITY_PILOT_CONTRACT = "semantic_authority_pilot_decision.v1"
SEMANTIC_AUTHORITY_PILOT_METRICS_CONTRACT = "semantic_authority_pilot_metrics.v1"
SEMANTIC_ACT_MIN_CONFIDENCE = 0.95
SEMANTIC_GOAL_MIN_CONFIDENCE = 0.50
LOW_RISK_SEMANTIC_ACTS = frozenset({"greeting"})


def semantic_authority_pilot_enabled() -> bool:
    value = os.getenv("SEMANTIC_AUTHORITY_PILOT_ENABLED", "true")
    return value.strip().lower() not in {"0", "false", "no", "off"}


def select_conversational_act_authority(
    *,
    legacy_act: Mapping[str, Any],
    semantic_projection: Any | None,
    semantic_representation: Any | None,
    enabled: bool,
    semantic_failure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    legacy_value = deepcopy(dict(legacy_act or {}))
    semantic_value: dict[str, Any] = {}
    field_diff: list[dict[str, Any]] = []
    confidence = 0.0
    agreement = False
    projection_valid = False
    validation_errors: list[str] = []
    critical_errors: list[str] = []
    forbidden_differences: list[str] = []
    rollback_reason = ""

    try:
        if semantic_failure:
            rollback_reason = "semantic_pipeline_exception"
            critical_errors.append(
                f"{semantic_failure.get('type') or 'SemanticPipelineError'}:"
                f"{semantic_failure.get('message') or 'semantic pipeline failed'}"
            )
        elif semantic_projection is None or semantic_representation is None:
            rollback_reason = "semantic_projection_unavailable"
            validation_errors.append("semantic_projection_unavailable")
        else:
            projection_data = _as_dict(semantic_projection)
            representation_data = _as_dict(semantic_representation)
            semantic_value = deepcopy(dict(projection_data.get("conversational_act") or {}))
            validation_errors = _validate_semantic_act(semantic_value)
            projection_valid = not validation_errors
            confidence = float(semantic_value.get("confidence") or 0.0)
            comparison = compare_semantic_projection(
                {"conversational_act": legacy_value},
                projection_data,
            )["projection_diff"]["conversational_act"]
            field_diff = deepcopy(list(comparison.get("field_diff") or []))
            agreement = comparison.get("status") == "MATCH"
            critical_errors = _critical_semantic_risks(representation_data, semantic_value)
            semantic_act = str(semantic_value.get("act") or "")
            if semantic_act not in LOW_RISK_SEMANTIC_ACTS:
                forbidden_differences.append(f"act_outside_pilot_scope:{semantic_act}")

            if not enabled:
                rollback_reason = "pilot_disabled"
            elif validation_errors:
                rollback_reason = "invalid_semantic_projection"
            elif critical_errors:
                rollback_reason = "critical_semantic_risk"
            elif confidence < SEMANTIC_ACT_MIN_CONFIDENCE:
                rollback_reason = "confidence_below_threshold"
            elif forbidden_differences:
                rollback_reason = "outside_low_risk_pilot_scope"
    except Exception as exc:
        semantic_value = {}
        projection_valid = False
        rollback_reason = "authority_evaluation_exception"
        critical_errors.append(f"{type(exc).__name__}:{exc}")

    if not enabled:
        authority_mode = "legacy"
        authority_reason = rollback_reason or "pilot_disabled"
        authority_selected = "legacy"
        selected_value = legacy_value
    elif rollback_reason:
        authority_mode = "rollback"
        authority_reason = rollback_reason
        authority_selected = "legacy"
        selected_value = legacy_value
    else:
        authority_mode = "semantic"
        authority_reason = "low_risk_semantic_act_promoted"
        authority_selected = "semantic"
        selected_value = semantic_value

    return {
        "contract": SEMANTIC_AUTHORITY_PILOT_CONTRACT,
        "consumer": "conversational_act",
        "authority_mode": authority_mode,
        "authority_reason": authority_reason,
        "authority_selected": authority_selected,
        "legacy_value": legacy_value,
        "semantic_value": semantic_value,
        "selected_value": deepcopy(selected_value),
        "field_diff": field_diff,
        "confidence": round(confidence, 4),
        "minimum_confidence": SEMANTIC_ACT_MIN_CONFIDENCE,
        "agreement": agreement,
        "projection_valid": projection_valid,
        "validation_errors": validation_errors,
        "critical_errors": critical_errors,
        "forbidden_differences": forbidden_differences,
        "rollback_reason": rollback_reason if authority_mode == "rollback" else "",
        "pilot_enabled": enabled,
        "pilot_scope": sorted(LOW_RISK_SEMANTIC_ACTS),
        "firewall_package": "FW-4",
        "legacy_capture_phase": "pre_semantic_compatibility",
        "downstream_text_access": False,
        "atomic_selection": True,
        "mixed_authority": False,
        "legacy_value_hash": _hash(legacy_value),
        "semantic_value_hash": _hash(semantic_value) if semantic_value else "",
        "selected_value_hash": _hash(selected_value),
    }


def conversational_act_trace(decision: Mapping[str, Any]) -> dict[str, Any]:
    selected = deepcopy(dict(decision.get("selected_value") or {}))
    authority = str(decision.get("authority_selected") or "legacy")
    return {
        "contract": "conversation_act_recognition.v1",
        "component": "semantic_projector" if authority == "semantic" else "conversation_state",
        "authority_mode": decision.get("authority_mode"),
        "authority_reason": decision.get("authority_reason"),
        "authority_selected": authority,
        "selected": selected,
        "legacy_selected": deepcopy(decision.get("legacy_value") or {}),
        "semantic_selected": deepcopy(decision.get("semantic_value") or {}),
        "field_diff": deepcopy(decision.get("field_diff") or []),
        "confidence": decision.get("confidence"),
        "rollback_reason": decision.get("rollback_reason"),
        "firewall_package": decision.get("firewall_package"),
        "legacy_capture_phase": decision.get("legacy_capture_phase"),
        "downstream_text_access": bool(decision.get("downstream_text_access")),
        "selected_value_hash": decision.get("selected_value_hash"),
        "atomic_selection": True,
        "mixed_authority": False,
        "decision_influence": authority == "semantic",
    }


def select_conversational_goal_authority(
    *,
    legacy_goal: Mapping[str, Any],
    semantic_goal: Mapping[str, Any],
    legacy_state_effect: Mapping[str, Any],
    semantic_state_effect: Mapping[str, Any],
    semantic_projection: Any | None,
    enabled: bool,
    semantic_failure: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    legacy_value = deepcopy(dict(legacy_goal or {}))
    semantic_value = deepcopy(dict(semantic_goal or {}))
    validation_errors: list[str] = []
    critical_errors: list[str] = []
    rollback_reason = ""
    confidence = 0.0
    projection_valid = False
    semantic_primary_goal: dict[str, Any] = {}

    try:
        if semantic_failure:
            rollback_reason = "semantic_pipeline_exception"
            critical_errors.append(
                f"{semantic_failure.get('type') or 'SemanticPipelineError'}:"
                f"{semantic_failure.get('message') or 'semantic pipeline failed'}"
            )
        elif semantic_projection is None:
            rollback_reason = "semantic_projection_unavailable"
            validation_errors.append("semantic_projection_unavailable")
        else:
            projection_data = _as_dict(semantic_projection)
            goal_projection = dict(projection_data.get("goal_projection") or {})
            semantic_primary_goal = deepcopy(
                dict(goal_projection.get("primary_goal") or {})
            )
            validation_errors = _validate_semantic_goal_input(
                goal_projection,
                semantic_primary_goal,
                semantic_value,
            )
            projection_valid = not validation_errors
            confidence = float(semantic_primary_goal.get("confidence") or 0.0)
            if not enabled:
                rollback_reason = "pilot_disabled"
            elif validation_errors:
                rollback_reason = "invalid_semantic_goal_projection"
            elif confidence < SEMANTIC_GOAL_MIN_CONFIDENCE:
                rollback_reason = "confidence_below_threshold"
    except Exception as exc:
        semantic_value = {}
        projection_valid = False
        rollback_reason = "authority_evaluation_exception"
        critical_errors.append(f"{type(exc).__name__}:{exc}")

    decision_agreement = _goal_decision_view(legacy_value) == _goal_decision_view(
        semantic_value
    )
    state_delta_parity = _as_plain_dict(legacy_state_effect) == _as_plain_dict(
        semantic_state_effect
    )
    field_diff = _top_level_field_diff(legacy_value, semantic_value)
    forbidden_differences: list[str] = []
    if semantic_value and not decision_agreement:
        forbidden_differences.append("goal_decision_fields_differ")
    if semantic_value and not state_delta_parity:
        forbidden_differences.append("goal_state_delta_differs")
    if enabled and not rollback_reason and forbidden_differences:
        rollback_reason = "forbidden_goal_difference"

    if not enabled:
        authority_mode = "legacy"
        authority_reason = rollback_reason or "pilot_disabled"
        authority_selected = "legacy"
        selected_value = legacy_value
    elif rollback_reason:
        authority_mode = "rollback"
        authority_reason = rollback_reason
        authority_selected = "legacy"
        selected_value = legacy_value
    else:
        authority_mode = "semantic"
        authority_reason = "structured_semantic_goal_input_selected"
        authority_selected = "semantic"
        selected_value = semantic_value

    return {
        "contract": SEMANTIC_AUTHORITY_PILOT_CONTRACT,
        "consumer": "conversational_goal",
        "authority_mode": authority_mode,
        "authority_reason": authority_reason,
        "authority_selected": authority_selected,
        "legacy_value": legacy_value,
        "semantic_value": semantic_value,
        "selected_value": deepcopy(selected_value),
        "semantic_primary_goal": semantic_primary_goal,
        "field_diff": field_diff,
        "confidence": round(confidence, 4),
        "minimum_confidence": SEMANTIC_GOAL_MIN_CONFIDENCE,
        "agreement": decision_agreement,
        "state_delta_parity": state_delta_parity,
        "legacy_state_effect": deepcopy(dict(legacy_state_effect or {})),
        "semantic_state_effect": deepcopy(dict(semantic_state_effect or {})),
        "projection_valid": projection_valid,
        "validation_errors": validation_errors,
        "critical_errors": critical_errors,
        "forbidden_differences": forbidden_differences,
        "rollback_reason": rollback_reason if authority_mode == "rollback" else "",
        "failure_reason": rollback_reason if authority_selected == "legacy" else "",
        "pilot_enabled": enabled,
        "firewall_package": "FW-5",
        "legacy_capture_phase": "structured_compatibility",
        "downstream_text_access": False,
        "atomic_selection": True,
        "mixed_authority": False,
        "legacy_value_hash": _hash(legacy_value),
        "semantic_value_hash": _hash(semantic_value) if semantic_value else "",
        "selected_value_hash": _hash(selected_value),
    }


def summarize_semantic_authority_pilot(
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    total = len(decisions)
    semantic_count = sum(item.get("authority_selected") == "semantic" for item in decisions)
    rollback_count = sum(item.get("authority_mode") == "rollback" for item in decisions)
    legacy_count = total - semantic_count
    agreement_count = sum(bool(item.get("agreement")) for item in decisions)
    failure_distribution = Counter(
        str(item.get("rollback_reason") or item.get("authority_reason") or "unknown")
        for item in decisions
        if item.get("authority_selected") != "semantic"
    )
    confidence_distribution = Counter(
        _confidence_bucket(float(item.get("confidence") or 0.0)) for item in decisions
    )
    return {
        "contract": SEMANTIC_AUTHORITY_PILOT_METRICS_CONTRACT,
        "consumer": "conversational_act",
        "turn_count": total,
        "promotion_count": semantic_count,
        "rollback_count": rollback_count,
        "legacy_count": legacy_count,
        "promotion_rate": _ratio(semantic_count, total),
        "rollback_rate": _ratio(rollback_count, total),
        "agreement_rate": _ratio(agreement_count, total),
        "semantic_authority_usage": {
            "count": semantic_count,
            "rate": _ratio(semantic_count, total),
        },
        "legacy_usage": {
            "count": legacy_count,
            "rate": _ratio(legacy_count, total),
        },
        "confidence_distribution": dict(sorted(confidence_distribution.items())),
        "failure_distribution": dict(sorted(failure_distribution.items())),
        "atomic_selection_violations": sum(
            not bool(item.get("atomic_selection")) or bool(item.get("mixed_authority"))
            for item in decisions
        ),
        "firewall_compliant_turns": sum(
            item.get("firewall_package") == "FW-4"
            and item.get("legacy_capture_phase") == "pre_semantic_compatibility"
            and item.get("downstream_text_access") is False
            for item in decisions
        ),
    }


def summarize_conversational_goal_authority(
    decisions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    total = len(decisions)
    semantic_count = sum(item.get("authority_selected") == "semantic" for item in decisions)
    rollback_count = sum(item.get("authority_mode") == "rollback" for item in decisions)
    legacy_count = total - semantic_count
    agreement_count = sum(bool(item.get("agreement")) for item in decisions)
    failure_distribution = Counter(
        str(item.get("failure_reason") or item.get("authority_reason") or "unknown")
        for item in decisions
        if item.get("authority_selected") != "semantic"
    )
    confidence_distribution = Counter(
        _confidence_bucket(float(item.get("confidence") or 0.0)) for item in decisions
    )
    return {
        "contract": SEMANTIC_AUTHORITY_PILOT_METRICS_CONTRACT,
        "consumer": "conversational_goal",
        "turn_count": total,
        "promotion_count": semantic_count,
        "rollback_count": rollback_count,
        "legacy_count": legacy_count,
        "promotion_rate": _ratio(semantic_count, total),
        "rollback_rate": _ratio(rollback_count, total),
        "agreement_rate": _ratio(agreement_count, total),
        "semantic_usage": {"count": semantic_count, "rate": _ratio(semantic_count, total)},
        "legacy_usage": {"count": legacy_count, "rate": _ratio(legacy_count, total)},
        "confidence_distribution": dict(sorted(confidence_distribution.items())),
        "failure_distribution": dict(sorted(failure_distribution.items())),
        "state_delta_parity_rate": _ratio(
            sum(bool(item.get("state_delta_parity")) for item in decisions),
            total,
        ),
        "atomic_selection_violations": sum(
            not bool(item.get("atomic_selection")) or bool(item.get("mixed_authority"))
            for item in decisions
        ),
        "firewall_compliant_turns": sum(
            item.get("firewall_package") == "FW-5"
            and item.get("downstream_text_access") is False
            for item in decisions
        ),
    }


def _validate_semantic_act(value: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if value.get("contract") != "conversational_act.v1":
        errors.append("invalid_contract")
    if not str(value.get("act") or "") or value.get("act") == "unknown":
        errors.append("missing_act")
    confidence = value.get("confidence")
    if not isinstance(confidence, (int, float)):
        errors.append("missing_confidence")
    elif not 0.0 <= float(confidence) <= 1.0:
        errors.append("confidence_out_of_range")
    if not isinstance(value.get("evidence"), Mapping):
        errors.append("missing_evidence")
    if not isinstance(value.get("impact"), Mapping):
        errors.append("missing_impact")
    return sorted(set(errors))


def _validate_semantic_goal_input(
    goal_projection: Mapping[str, Any],
    primary_goal: Mapping[str, Any],
    projected_goal: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    if goal_projection.get("contract") != "goal_projection.v1":
        errors.append("invalid_goal_projection_contract")
    if not primary_goal:
        errors.append("missing_primary_goal")
    elif not str(primary_goal.get("type") or ""):
        errors.append("missing_primary_goal_type")
    confidence = primary_goal.get("confidence")
    if not isinstance(confidence, (int, float)):
        errors.append("missing_goal_confidence")
    elif not 0.0 <= float(confidence) <= 1.0:
        errors.append("goal_confidence_out_of_range")
    if projected_goal.get("contract") != "conversational_goal.v1":
        errors.append("invalid_conversational_goal_contract")
    required = {
        "originating_act",
        "intention",
        "strategy",
        "success_criteria",
        "abandonment_criteria",
        "priority",
        "mission_impact",
        "evidence",
        "fulfillment",
    }
    missing = sorted(required - set(projected_goal))
    errors.extend(f"missing_conversational_goal_field:{field}" for field in missing)
    return sorted(set(errors))


def _goal_decision_view(goal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(goal.get(key))
        for key in (
            "contract",
            "originating_act",
            "act",
            "intention",
            "strategy",
            "success_criteria",
            "abandonment_criteria",
            "priority",
            "mission_impact",
            "fulfillment",
            "component",
            "turn",
        )
    }


def _top_level_field_diff(
    legacy: Mapping[str, Any],
    semantic: Mapping[str, Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for field in sorted(set(legacy) | set(semantic)):
        legacy_value = deepcopy(legacy.get(field))
        semantic_value = deepcopy(semantic.get(field))
        if legacy_value == semantic_value:
            status = "MATCH"
        elif field not in semantic:
            status = "MISSING"
        elif field not in legacy:
            status = "EXTRA"
        else:
            status = "DIFFERENT"
        output.append(
            {
                "field": field,
                "status": status,
                "legacy": legacy_value,
                "semantic": semantic_value,
            }
        )
    return output


def _as_plain_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy(dict(value or {}))


def _critical_semantic_risks(
    representation: Mapping[str, Any],
    semantic_act: Mapping[str, Any],
) -> list[str]:
    errors: list[str] = []
    grounding = representation.get("grounding") or {}
    topic_structure = representation.get("topic_structure") or {}
    if grounding.get("unresolved_coreferences"):
        errors.append("unresolved_coreference")
    if representation.get("corrections"):
        errors.append("correction_or_retraction")
    if representation.get("contradictions"):
        errors.append("contradiction")
    if representation.get("uncertainty"):
        errors.append("semantic_uncertainty")
    if topic_structure.get("multiple_topics"):
        errors.append("multiple_topics")
    people = {
        str(item.get("value") or "")
        for item in representation.get("entities") or []
        if item.get("type") == "person" and item.get("value")
    }
    if len(people) > 1:
        errors.append("multiple_people")
    if semantic_act.get("act") == "greeting" and (
        representation.get("intents") or [{}]
    )[0].get("type") != "greet":
        errors.append("greeting_intent_mismatch")
    return errors


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise TypeError(f"Expected semantic mapping, got {type(value).__name__}")
    return deepcopy(dict(value))


def _hash(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _confidence_bucket(value: float) -> str:
    if value < 0.60:
        return "0.00-0.59"
    if value < 0.80:
        return "0.60-0.79"
    if value < 0.95:
        return "0.80-0.94"
    return "0.95-1.00"


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
