from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable, Mapping, Sequence

from aca_core.text import normalize_text
from aca_kernel.core.events import Event
from aca_os.semantic_authority import SEMANTIC_AUTHORITY_VERSION, SemanticAuthority
from aca_os.semantic_understanding_evaluation import (
    load_semantic_understanding_benchmark,
    run_semantic_understanding_evaluation,
)


DEFAULT_ADVERSARIAL_BENCHMARK = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "semantic"
    / "aca_semantic_adversarial_benchmark_v1.json"
)

ROBUSTNESS_WEIGHTS = {
    "semantic_accuracy": 0.30,
    "semantic_stability": 0.10,
    "consistency_score": 0.10,
    "recovery_score": 0.10,
    "context_retention": 0.10,
    "long_conversation_accuracy": 0.10,
    "noise_resistance": 0.075,
    "ambiguity_robustness": 0.075,
    "confidence_calibration_score": 0.05,
}

ERROR_CLASSIFICATIONS = (
    "Entity Failure",
    "Coreference Failure",
    "Negation Failure",
    "Temporal Failure",
    "Memory Failure",
    "Multi-topic Failure",
    "Priority Failure",
    "Ambiguity Failure",
    "Provenance Failure",
    "Correction Failure",
    "Retraction Failure",
    "Event Failure",
    "Speaker Attribution Failure",
    "Semantic Consistency Failure",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass
class AdversarialEvaluationContext:
    conversation_id: str
    turn_count: int = 0
    confirmed_facts: dict[str, Any] = field(default_factory=dict)
    topic_stack: list[dict[str, Any]] = field(default_factory=list)
    pending_questions: list[dict[str, Any]] = field(default_factory=list)
    relevant_context: dict[str, Any] = field(default_factory=dict)
    active_mission: dict[str, Any] | None = None


def load_adversarial_benchmark(path: str | Path | None = None) -> dict[str, Any]:
    benchmark_path = Path(path) if path else DEFAULT_ADVERSARIAL_BENCHMARK
    manifest = json.loads(benchmark_path.read_text(encoding="utf-8"))
    variant_sets = dict(manifest.get("variant_sets") or {})
    conversations: list[dict[str, Any]] = []

    for profile in manifest.get("profiles") or []:
        profile_id = str(profile["id"])
        variants_name = str(profile.get("variants") or "")
        variants = list(variant_sets.get(variants_name) or [])
        if not variants:
            raise ValueError(f"Adversarial profile {profile_id!r} has no variants")
        for variant_index, variant in enumerate(variants, start=1):
            values = _StrictFormatDict({str(key): value for key, value in dict(variant).items()})
            turns = _expand_turns(
                profile.get("turns") or [],
                values=values,
                profile_categories=list(profile.get("categories") or []),
            )
            conversations.append(
                {
                    "id": f"{profile_id}:{variant_index:02d}",
                    "profile": profile_id,
                    "variant": variant_index,
                    "categories": list(profile.get("categories") or []),
                    "turns": turns,
                }
            )

    official = load_semantic_understanding_benchmark()
    official_messages = {
        normalize_text(turn["message"])
        for conversation in official["conversations"]
        for turn in conversation["turns"]
    }
    adversarial_messages = [
        turn["message"]
        for conversation in conversations
        for turn in conversation["turns"]
    ]
    overlap = sorted(
        {
            message
            for message in adversarial_messages
            if normalize_text(message) in official_messages
        }
    )
    if overlap:
        raise ValueError(f"Adversarial corpus overlaps SA-2.5: {overlap[:5]}")

    long_messages = [message for message in adversarial_messages if len(message.split()) > 2000]
    stress_conversations = [
        conversation
        for conversation in conversations
        if len(conversation["turns"]) >= int(manifest.get("minimum_stress_turns") or 51)
    ]
    if len(conversations) < int(manifest.get("minimum_conversations") or 100):
        raise ValueError("Adversarial corpus has fewer conversations than required")
    if not long_messages:
        raise ValueError("Adversarial corpus has no message over 2,000 words")
    if not stress_conversations:
        raise ValueError("Adversarial corpus has no conversation over 50 turns")

    expanded = {
        "contract": manifest.get("contract"),
        "version": manifest.get("version"),
        "name": manifest.get("name"),
        "description": manifest.get("description"),
        "context_policy": manifest.get("context_policy"),
        "conversation_count": len(conversations),
        "turn_count": len(adversarial_messages),
        "unique_message_count": len(set(adversarial_messages)),
        "official_message_overlap_count": len(overlap),
        "long_message_count": len(long_messages),
        "maximum_message_words": max(len(message.split()) for message in adversarial_messages),
        "stress_conversation_count": len(stress_conversations),
        "maximum_conversation_turns": max(len(item["turns"]) for item in conversations),
        "conversations": conversations,
    }
    expanded["benchmark_hash"] = _sha256(expanded)
    return expanded


class _StrictFormatDict(dict):
    def __missing__(self, key: str) -> str:
        raise KeyError(f"Missing adversarial template value: {key}")


def _format_recursive(value: Any, values: Mapping[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format_map(values)
    if isinstance(value, list):
        return [_format_recursive(item, values) for item in value]
    if isinstance(value, dict):
        return {str(key): _format_recursive(item, values) for key, item in value.items()}
    return value


def _expand_turns(
    specifications: Sequence[Mapping[str, Any]],
    *,
    values: Mapping[str, Any],
    profile_categories: Sequence[str],
) -> list[dict[str, Any]]:
    turns: list[dict[str, Any]] = []

    def append_turn(specification: Mapping[str, Any], scoped_values: Mapping[str, Any]) -> None:
        formatted = _format_recursive(deepcopy(specification), scoped_values)
        if "long_message" in formatted:
            long_form = dict(formatted.pop("long_message"))
            message = (
                str(long_form.get("prefix") or "")
                + str(long_form.get("filler") or "") * int(long_form.get("repeat") or 0)
                + str(long_form.get("suffix") or "")
            )
        else:
            message = str(formatted.pop("message"))
        turns.append(
            {
                "turn": len(turns) + 1,
                "message": message,
                "categories": _unique(list(profile_categories) + list(formatted.pop("tags", []))),
                "expected": dict(formatted.pop("expected", {})),
                "recovery_checkpoint": bool(formatted.pop("recovery_checkpoint", False)),
                "consistency_checkpoint": bool(formatted.pop("consistency_checkpoint", False)),
                "context_checkpoint": bool(formatted.pop("context_checkpoint", False)),
            }
        )

    for specification in specifications:
        if "repeat_cycle" not in specification:
            append_turn(specification, values)
            continue
        cycle = dict(specification["repeat_cycle"])
        templates = list(cycle.get("templates") or [])
        for repeat_index in range(1, int(cycle.get("count") or 0) + 1):
            scoped = _StrictFormatDict(dict(values))
            scoped["repeat_index"] = repeat_index
            append_turn(templates[(repeat_index - 1) % len(templates)], scoped)
    return turns


def _unique(values: Sequence[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value not in output:
            output.append(value)
    return output


def _observable_semantics(representation: Mapping[str, Any]) -> dict[str, Any]:
    grounding = dict(representation.get("grounding") or {})
    entities = [dict(item) for item in representation.get("entities") or []]
    facts = [
        dict(item)
        for item in representation.get("assertions") or []
        if item.get("predicate") not in {"user_statement", "user_question"}
    ]
    goals = [dict(item) for item in representation.get("goals") or []]
    topics = [
        dict(item)
        for item in (representation.get("topic_structure") or {}).get("topics") or []
    ]
    intents = sorted(
        [dict(item) for item in representation.get("intents") or []],
        key=lambda item: (int(item.get("priority") or 999), -float(item.get("confidence") or 0.0)),
    )
    unresolved = [dict(item) for item in grounding.get("unresolved_coreferences") or []]
    ambiguity = bool(representation.get("uncertainty")) or bool(unresolved) or any(
        not item.get("target") for item in representation.get("corrections") or []
    )
    return {
        "entities": entities,
        "facts": facts,
        "events": [dict(item) for item in representation.get("events") or []],
        "goals": goals,
        "topics": topics,
        "intents": intents,
        "primary_intent": str((intents[0] if intents else {}).get("type") or ""),
        "conversational_act": (representation.get("conversational_act") or {}).get("act"),
        "corrections": [dict(item) for item in representation.get("corrections") or []],
        "contradictions": [dict(item) for item in representation.get("contradictions") or []],
        "coreferences": [dict(item) for item in grounding.get("resolved_coreferences") or []],
        "unresolved_coreferences": unresolved,
        "temporal": [
            dict(item) for item in entities if item.get("type") == "temporal_expression"
        ],
        "ambiguity": ambiguity,
        "confidence": _mean_confidence(representation),
    }


def _mean_confidence(representation: Mapping[str, Any]) -> float:
    values: list[float] = []
    for field_name in (
        "entities",
        "events",
        "assertions",
        "intents",
        "goals",
        "uncertainty",
        "corrections",
        "contradictions",
    ):
        values.extend(
            float(item["confidence"])
            for item in representation.get(field_name) or []
            if item.get("confidence") is not None
        )
    values.extend(
        float(item["confidence"])
        for item in (representation.get("topic_structure") or {}).get("topics") or []
        if item.get("confidence") is not None
    )
    values.extend(
        float(item["confidence"])
        for item in (representation.get("grounding") or {}).get("resolved_coreferences") or []
        if item.get("confidence") is not None
    )
    act_confidence = (representation.get("conversational_act") or {}).get("confidence")
    if act_confidence is not None:
        values.append(float(act_confidence))
    return round(fmean(values), 4) if values else 0.0


def run_adversarial_semantic_evaluation(
    *,
    conversation_ids: Iterable[str] | None = None,
    profile_ids: Iterable[str] | None = None,
    path: str | Path | None = None,
    compare_official: bool = True,
) -> dict[str, Any]:
    benchmark = load_adversarial_benchmark(path)
    selected_conversations = set(conversation_ids or [])
    selected_profiles = set(profile_ids or [])
    conversations = [
        conversation
        for conversation in benchmark["conversations"]
        if (not selected_conversations or conversation["id"] in selected_conversations)
        and (not selected_profiles or conversation["profile"] in selected_profiles)
    ]
    authority = SemanticAuthority()
    conversation_results: list[dict[str, Any]] = []
    all_errors: list[dict[str, Any]] = []
    all_turns: list[dict[str, Any]] = []

    for conversation in conversations:
        context = AdversarialEvaluationContext(conversation_id=conversation["id"])
        turn_results: list[dict[str, Any]] = []
        for turn in conversation["turns"]:
            representation = authority.interpret(
                Event(
                    type="user_message",
                    payload=turn["message"],
                    metadata={"conversation_id": conversation["id"]},
                ),
                conversation_state=context,
                turn_number=turn["turn"],
            ).to_dict()
            actual = _observable_semantics(representation)
            checks, errors = _evaluate_expected(
                expected=turn["expected"],
                actual=actual,
                representation=representation,
                conversation_id=conversation["id"],
                turn_number=turn["turn"],
                message=turn["message"],
                categories=turn["categories"],
            )
            score = round(fmean(check["score"] for check in checks), 4) if checks else 1.0
            confidence = float(actual["confidence"])
            calibration_error = round(abs(confidence - score), 4)
            overconfident = confidence >= 0.8 and score < 0.5
            turn_result = {
                "turn": turn["turn"],
                "message": turn["message"],
                "message_words": len(turn["message"].split()),
                "categories": list(turn["categories"]),
                "expected": deepcopy(turn["expected"]),
                "actual": _compact_actual(actual),
                "checks": checks,
                "score": score,
                "confidence": confidence,
                "calibration_error": calibration_error,
                "overconfident_error": overconfident,
                "error_count": len(errors),
                "recovery_checkpoint": turn["recovery_checkpoint"],
                "consistency_checkpoint": turn["consistency_checkpoint"],
                "context_checkpoint": turn["context_checkpoint"],
                "structural_signature": _structural_signature(actual),
                "errors": errors,
            }
            turn_results.append(turn_result)
            all_turns.append(
                {
                    **turn_result,
                    "conversation_id": conversation["id"],
                    "profile": conversation["profile"],
                }
            )
            all_errors.extend(errors)
            _advance_gold_context(context, turn["expected"], turn["turn"])

        conversation_score = round(fmean(turn["score"] for turn in turn_results), 4)
        conversation_results.append(
            {
                "id": conversation["id"],
                "profile": conversation["profile"],
                "categories": list(conversation["categories"]),
                "turn_count": len(turn_results),
                "score": conversation_score,
                "error_count": sum(turn["error_count"] for turn in turn_results),
                "overconfident_error_count": sum(
                    int(turn["overconfident_error"]) for turn in turn_results
                ),
                "turns": turn_results,
            }
        )

    metrics = _robustness_metrics(conversation_results, all_turns, all_errors)
    classifications = Counter(error["classification"] for error in all_errors)
    severities = Counter(error["severity"] for error in all_errors)
    categories = _category_results(all_turns)
    official_result = run_semantic_understanding_evaluation() if compare_official else None
    comparison = _benchmark_comparison(benchmark, metrics, official_result)
    recommendation = _promotion_recommendation(metrics, comparison)
    worst_cases = [
        {
            "rank": index,
            "conversation_id": conversation["id"],
            "profile": conversation["profile"],
            "turn_count": conversation["turn_count"],
            "score": conversation["score"],
            "error_count": conversation["error_count"],
            "overconfident_error_count": conversation["overconfident_error_count"],
            "worst_turns": [
                {
                    "turn": turn["turn"],
                    "score": turn["score"],
                    "message": turn["message"][:500],
                    "classifications": sorted(
                        {error["classification"] for error in turn["errors"]}
                    ),
                }
                for turn in sorted(
                    conversation["turns"],
                    key=lambda item: (item["score"], -item["error_count"], item["turn"]),
                )[:5]
            ],
        }
        for index, conversation in enumerate(
            sorted(
                conversation_results,
                key=lambda item: (item["score"], -item["error_count"], item["id"]),
            )[:100],
            start=1,
        )
    ]
    frequent_errors = _frequent_errors(all_errors)
    result = {
        "contract": "semantic_adversarial_evaluation_result.v1",
        "benchmark": {
            key: benchmark[key]
            for key in (
                "contract",
                "version",
                "benchmark_hash",
                "context_policy",
                "conversation_count",
                "turn_count",
                "unique_message_count",
                "official_message_overlap_count",
                "long_message_count",
                "maximum_message_words",
                "stress_conversation_count",
                "maximum_conversation_turns",
            )
        },
        "engine": {
            "component": "semantic_authority",
            "version": SEMANTIC_AUTHORITY_VERSION,
            "mode": "shadow",
            "official_authority": "legacy",
            "runtime_used": False,
            "decision_influence": False,
            "state_mutation": False,
            "provider_calls": 0,
        },
        "metrics": metrics,
        "confidence_calibration": {
            "mean_confidence": _mean(turn["confidence"] for turn in all_turns),
            "mean_turn_score": _mean(turn["score"] for turn in all_turns),
            "mean_absolute_calibration_error": _mean(
                turn["calibration_error"] for turn in all_turns
            ),
            "overconfident_error_count": sum(
                int(turn["overconfident_error"]) for turn in all_turns
            ),
            "overconfident_error_rate": _ratio(
                sum(int(turn["overconfident_error"]) for turn in all_turns),
                len(all_turns),
            ),
        },
        "benchmark_comparison": comparison,
        "recommendation": recommendation,
        "categories": categories,
        "error_classification": {
            "counts": {name: classifications.get(name, 0) for name in ERROR_CLASSIFICATIONS},
            "severity_counts": dict(sorted(severities.items())),
            "total_errors": len(all_errors),
            "critical_failure_rate": _ratio(severities.get("critical", 0), len(all_turns)),
            "systematic": [
                item for item in frequent_errors if item["count"] >= 5
            ],
            "isolated": [
                item for item in frequent_errors if item["count"] < 5
            ],
        },
        "strengths": _metric_bands(metrics, minimum=0.85, keep_above=True),
        "weaknesses": _metric_bands(metrics, minimum=0.70, keep_above=False),
        "frequent_errors": frequent_errors,
        "worst_cases": worst_cases,
        "conversations": conversation_results,
        "reproducibility": {
            "deterministic": True,
            "benchmark_hash": benchmark["benchmark_hash"],
            "official_benchmark_hash": comparison.get("official_benchmark_hash"),
        },
    }
    result["report_hash"] = _sha256(result)
    return result


def _compact_actual(actual: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "entities": [
            {key: item.get(key) for key in ("type", "value", "role")}
            for item in actual.get("entities") or []
        ],
        "facts": [
            {key: item.get(key) for key in ("subject", "predicate", "value", "polarity")}
            for item in actual.get("facts") or []
        ],
        "events": [item.get("type") for item in actual.get("events") or []],
        "topics": [item.get("type") for item in actual.get("topics") or []],
        "intents": [item.get("type") for item in actual.get("intents") or []],
        "goals": [item.get("target") for item in actual.get("goals") or []],
        "corrections": [item.get("operation") for item in actual.get("corrections") or []],
        "coreferences": [
            {key: item.get(key) for key in ("mention", "target_type", "target_value")}
            for item in actual.get("coreferences") or []
        ],
        "unresolved_coreferences": [
            item.get("mention") for item in actual.get("unresolved_coreferences") or []
        ],
        "temporal": [item.get("value") for item in actual.get("temporal") or []],
        "ambiguity": actual.get("ambiguity"),
    }


def _evaluate_expected(
    *,
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    representation: Mapping[str, Any],
    conversation_id: str,
    turn_number: int,
    message: str,
    categories: Sequence[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    actual_by_field: dict[str, list[Any]] = {
        "entities": list(actual.get("entities") or []),
        "facts": list(actual.get("facts") or []),
        "events": list(actual.get("events") or []),
        "topics": [item.get("type") for item in actual.get("topics") or []],
        "corrections": [item.get("operation") for item in actual.get("corrections") or []],
        "contradictions": list(actual.get("contradictions") or []),
        "coreferences": list(actual.get("coreferences") or []),
        "temporal": [item.get("value") for item in actual.get("temporal") or []],
        "speaker_facts": list(actual.get("facts") or []),
        "goals": list(actual.get("goals") or []),
    }
    for field_name in (
        "entities",
        "facts",
        "events",
        "topics",
        "corrections",
        "contradictions",
        "coreferences",
        "temporal",
        "speaker_facts",
        "goals",
    ):
        if field_name not in expected:
            continue
        expected_items = list(expected.get(field_name) or [])
        actual_items = actual_by_field[field_name]
        matched_expected, matched_actual = _match_expected_items(
            field_name,
            expected_items,
            actual_items,
        )
        score = _set_f1(len(matched_expected), len(expected_items), len(actual_items))
        passed = len(matched_expected) == len(expected_items) and len(matched_actual) == len(actual_items)
        checks.append(
            {
                "name": field_name,
                "score": score,
                "expected": deepcopy(expected_items),
                "actual": deepcopy(actual_items),
                "matched_expected": len(matched_expected),
                "matched_actual": len(matched_actual),
                "passed": passed,
            }
        )
        if not passed:
            errors.append(
                _adversarial_error(
                    field_name=field_name,
                    expected=expected_items,
                    actual=actual_items,
                    difference=_set_difference(
                        matched_expected,
                        matched_actual,
                        len(expected_items),
                        len(actual_items),
                    ),
                    conversation_id=conversation_id,
                    turn_number=turn_number,
                    message=message,
                    categories=categories,
                )
            )

    if "goal_contains" in expected:
        expected_goal = normalize_text(str(expected.get("goal_contains") or ""))
        actual_goals = [normalize_text(str(item.get("target") or "")) for item in actual.get("goals") or []]
        passed = any(expected_goal and expected_goal in target for target in actual_goals)
        checks.append(
            {
                "name": "goal_contains",
                "score": 1.0 if passed else 0.0,
                "expected": expected.get("goal_contains"),
                "actual": actual_goals,
                "passed": passed,
            }
        )
        if not passed:
            errors.append(
                _adversarial_error(
                    field_name="goal_contains",
                    expected=expected.get("goal_contains"),
                    actual=actual_goals,
                    difference="expected_priority_goal_missing",
                    conversation_id=conversation_id,
                    turn_number=turn_number,
                    message=message,
                    categories=categories,
                )
            )

    if "ambiguity" in expected:
        expected_ambiguity = bool(expected.get("ambiguity"))
        actual_ambiguity = bool(actual.get("ambiguity"))
        passed = expected_ambiguity == actual_ambiguity
        checks.append(
            {
                "name": "ambiguity",
                "score": 1.0 if passed else 0.0,
                "expected": expected_ambiguity,
                "actual": actual_ambiguity,
                "passed": passed,
            }
        )
        if not passed:
            errors.append(
                _adversarial_error(
                    field_name="ambiguity",
                    expected=expected_ambiguity,
                    actual=actual_ambiguity,
                    difference="ambiguity_calculation_mismatch",
                    conversation_id=conversation_id,
                    turn_number=turn_number,
                    message=message,
                    categories=categories,
                )
            )

    provenance_score, provenance_detail = _provenance_score(representation)
    provenance_passed = math.isclose(provenance_score, 1.0)
    checks.append(
        {
            "name": "provenance",
            "score": provenance_score,
            "expected": "complete_source_evidence",
            "actual": provenance_detail,
            "passed": provenance_passed,
        }
    )
    if not provenance_passed:
        errors.append(
            _adversarial_error(
                field_name="provenance",
                expected="complete_source_evidence",
                actual=provenance_detail,
                difference="semantic_items_without_complete_provenance",
                conversation_id=conversation_id,
                turn_number=turn_number,
                message=message,
                categories=categories,
            )
        )
    return checks, errors


def _match_expected_items(
    field_name: str,
    expected: Sequence[Any],
    actual: Sequence[Any],
) -> tuple[set[int], set[int]]:
    matched_expected: set[int] = set()
    matched_actual: set[int] = set()
    for expected_index, expected_item in enumerate(expected):
        for actual_index, actual_item in enumerate(actual):
            if actual_index in matched_actual:
                continue
            if _adversarial_item_matches(field_name, expected_item, actual_item):
                matched_expected.add(expected_index)
                matched_actual.add(actual_index)
                break
    return matched_expected, matched_actual


def _adversarial_item_matches(field_name: str, expected: Any, actual: Any) -> bool:
    if field_name in {"topics", "corrections", "temporal"}:
        return _normalized_value(expected) == _normalized_value(actual)
    if not isinstance(expected, Mapping) or not isinstance(actual, Mapping):
        return _normalized_value(expected) == _normalized_value(actual)
    if field_name == "goals":
        owner = expected.get("owner")
        contains = normalize_text(str(expected.get("contains") or ""))
        if owner is not None and _normalized_value(owner) != _normalized_value(actual.get("owner")):
            return False
        return bool(contains) and contains in normalize_text(str(actual.get("target") or ""))
    if field_name == "speaker_facts":
        expected_mapping = {
            "subject": expected.get("speaker"),
            "predicate": expected.get("predicate"),
            "value": expected.get("value"),
        }
    else:
        expected_mapping = expected
    return all(
        _normalized_value(value) == _normalized_value(actual.get(key))
        for key, value in expected_mapping.items()
    )


def _normalized_value(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, Mapping):
        return {str(key): _normalized_value(item) for key, item in sorted(value.items())}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_normalized_value(item) for item in value]
    return value


def _set_f1(true_positive: int, expected: int, actual: int) -> float:
    if expected == 0 and actual == 0:
        return 1.0
    if expected + actual == 0:
        return 0.0
    return round((2.0 * true_positive) / (expected + actual), 4)


def _set_difference(
    matched_expected: set[int],
    matched_actual: set[int],
    expected_count: int,
    actual_count: int,
) -> str:
    missing = expected_count - len(matched_expected)
    extra = actual_count - len(matched_actual)
    if missing and extra:
        return "missing_expected_and_unexpected_extra_items"
    if missing:
        return "missing_expected_semantic_items"
    return "unexpected_extra_semantic_items"


def _provenance_score(representation: Mapping[str, Any]) -> tuple[float, dict[str, Any]]:
    semantic_items: list[tuple[str, Mapping[str, Any]]] = []
    for field_name in (
        "entities",
        "events",
        "assertions",
        "goals",
        "uncertainty",
        "corrections",
        "contradictions",
    ):
        semantic_items.extend(
            (field_name, item)
            for item in representation.get(field_name) or []
            if isinstance(item, Mapping)
        )
    semantic_items.extend(
        ("topics", item)
        for item in (representation.get("topic_structure") or {}).get("topics") or []
        if isinstance(item, Mapping)
    )
    semantic_items.extend(
        ("coreferences", item)
        for item in (representation.get("grounding") or {}).get("resolved_coreferences") or []
        if isinstance(item, Mapping)
    )
    if not semantic_items:
        return 1.0, {"item_count": 0, "complete_count": 0, "incomplete": []}
    incomplete: list[dict[str, Any]] = []
    for field_name, item in semantic_items:
        evidence = item.get("evidence") if isinstance(item.get("evidence"), Mapping) else {}
        has_source_reference = bool(
            evidence.get("segment_id")
            or evidence.get("segment_ids")
            or evidence.get("source_state_key")
        )
        has_evidence_content = bool(
            evidence.get("span")
            or evidence.get("text")
            or evidence.get("segment_ids")
            or evidence.get("source_state_key")
        )
        complete = (
            item.get("confidence") is not None
            and bool(item.get("rule") or evidence.get("rule"))
            and has_source_reference
            and has_evidence_content
        )
        if not complete:
            incomplete.append(
                {
                    "field": field_name,
                    "id": next(
                        (
                            item.get(key)
                            for key in (
                                "entity_id",
                                "event_id",
                                "assertion_id",
                                "goal_id",
                                "topic_id",
                                "correction_id",
                                "contradiction_id",
                            )
                            if item.get(key)
                        ),
                        None,
                    ),
                    "missing": [
                        name
                        for name, present in (
                            ("confidence", item.get("confidence") is not None),
                            ("rule", bool(item.get("rule") or evidence.get("rule"))),
                            ("source_reference", has_source_reference),
                            ("evidence_content", has_evidence_content),
                        )
                        if not present
                    ],
                }
            )
    complete_count = len(semantic_items) - len(incomplete)
    return (
        round(complete_count / len(semantic_items), 4),
        {
            "item_count": len(semantic_items),
            "complete_count": complete_count,
            "incomplete": incomplete[:25],
        },
    )


def _adversarial_error(
    *,
    field_name: str,
    expected: Any,
    actual: Any,
    difference: str,
    conversation_id: str,
    turn_number: int,
    message: str,
    categories: Sequence[str],
) -> dict[str, Any]:
    classification = _error_classification(field_name, categories)
    severity = _error_severity(classification, categories)
    return {
        "error_id": f"{conversation_id}:turn-{turn_number}:{field_name}:{difference}",
        "conversation_id": conversation_id,
        "turn": turn_number,
        "message": message[:1000],
        "message_words": len(message.split()),
        "field": field_name,
        "categories": list(categories),
        "classification": classification,
        "severity": severity,
        "expected": deepcopy(expected),
        "actual": deepcopy(actual),
        "difference": difference,
    }


def _error_classification(field_name: str, categories: Sequence[str]) -> str:
    category_set = set(categories)
    if field_name == "entities":
        return "Entity Failure"
    if field_name == "coreferences":
        if category_set & {"memory", "distant_memory", "context_retention"}:
            return "Memory Failure"
        return "Coreference Failure"
    if field_name == "facts":
        if category_set & {"negation", "double_negation", "triple_negation"}:
            return "Negation Failure"
        return "Semantic Consistency Failure"
    if field_name == "temporal":
        return "Temporal Failure"
    if field_name == "topics":
        return "Multi-topic Failure"
    if field_name in {"goals", "goal_contains"}:
        return "Priority Failure"
    if field_name == "ambiguity":
        return "Ambiguity Failure"
    if field_name == "provenance":
        return "Provenance Failure"
    if field_name == "corrections":
        if category_set & {"retraction", "successive_retraction"}:
            return "Retraction Failure"
        return "Correction Failure"
    if field_name == "events":
        return "Event Failure"
    if field_name == "speaker_facts":
        return "Speaker Attribution Failure"
    return "Semantic Consistency Failure"


def _error_severity(classification: str, categories: Sequence[str]) -> str:
    if classification in {"Speaker Attribution Failure", "Memory Failure"}:
        return "critical"
    if classification == "Negation Failure" and set(categories) & {
        "double_negation",
        "triple_negation",
        "contradiction",
    }:
        return "critical"
    if classification in {
        "Coreference Failure",
        "Negation Failure",
        "Priority Failure",
        "Semantic Consistency Failure",
    }:
        return "high"
    if classification in {
        "Multi-topic Failure",
        "Ambiguity Failure",
        "Correction Failure",
        "Retraction Failure",
        "Event Failure",
    }:
        return "medium"
    return "low"


def _advance_gold_context(
    context: AdversarialEvaluationContext,
    expected: Mapping[str, Any],
    turn_number: int,
) -> None:
    for fact in expected.get("facts") or []:
        predicate = str(fact.get("predicate") or "")
        if predicate:
            context.confirmed_facts[predicate] = {
                "contract": "conversational_fact.v1",
                "type": predicate,
                "value": deepcopy(fact.get("value")),
                "status": "active",
                "origin": "semantic_adversarial_gold",
                "confidence": 1.0,
            }
    for fact in expected.get("speaker_facts") or []:
        predicate = f"{normalize_text(fact.get('speaker') or '')}:{fact.get('predicate') or ''}"
        context.confirmed_facts[predicate] = {
            "contract": "conversational_fact.v1",
            "type": fact.get("predicate"),
            "subject": fact.get("speaker"),
            "value": deepcopy(fact.get("value")),
            "status": "active",
            "origin": "semantic_adversarial_gold",
            "confidence": 1.0,
        }
    for entity in expected.get("entities") or []:
        key = f"entity:{entity.get('type')}:{normalize_text(str(entity.get('value') or ''))}"
        context.relevant_context[key] = deepcopy(entity)
    topics = list(expected.get("topics") or [])
    if topics:
        context.topic_stack = [
            {
                "id": f"adversarial-gold-topic:{topic}",
                "topic_id": f"adversarial-gold-topic:{topic}",
                "type": topic,
                "status": "active" if index == 0 else "suspended",
            }
            for index, topic in enumerate(topics)
        ]
    context.turn_count = turn_number


def _structural_signature(actual: Mapping[str, Any]) -> str:
    structure = {
        "entities": sorted(
            (str(item.get("type") or ""), str(item.get("role") or ""))
            for item in actual.get("entities") or []
        ),
        "facts": sorted(
            (
                str(item.get("predicate") or ""),
                item.get("value") if isinstance(item.get("value"), bool) else type(item.get("value")).__name__,
                str(item.get("polarity") or ""),
            )
            for item in actual.get("facts") or []
        ),
        "events": sorted(str(item.get("type") or "") for item in actual.get("events") or []),
        "topics": sorted(str(item.get("type") or "") for item in actual.get("topics") or []),
        "intents": sorted(str(item.get("type") or "") for item in actual.get("intents") or []),
        "goals": sorted(str(item.get("type") or "") for item in actual.get("goals") or []),
        "corrections": sorted(str(item.get("operation") or "") for item in actual.get("corrections") or []),
        "coreferences": sorted(
            (
                normalize_text(str(item.get("mention") or "")),
                str(item.get("target_type") or ""),
            )
            for item in actual.get("coreferences") or []
        ),
        "ambiguity": bool(actual.get("ambiguity")),
        "conversational_act": actual.get("conversational_act"),
    }
    return _sha256(structure)


def _robustness_metrics(
    conversations: Sequence[Mapping[str, Any]],
    turns: Sequence[Mapping[str, Any]],
    errors: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    long_conversation_ids = {
        conversation["id"]
        for conversation in conversations
        if int(conversation.get("turn_count") or 0) > 50
    }
    noise_categories = {
        "noise",
        "whatsapp",
        "orthography",
        "emoji",
        "audio_transcript",
        "autocorrection",
        "irony",
        "sarcasm",
        "humor",
    }
    ambiguity_categories = {
        "ambiguity",
        "real_ambiguity",
        "ambiguous_reference",
        "no_correct_answer",
    }
    signature_groups: dict[tuple[str, int], list[str]] = defaultdict(list)
    for turn in turns:
        signature_groups[(str(turn["profile"]), int(turn["turn"]))].append(
            str(turn["structural_signature"])
        )
    stability_scores = [
        max(Counter(signatures).values()) / len(signatures)
        for signatures in signature_groups.values()
        if signatures
    ]
    calibration_error = _mean(turn["calibration_error"] for turn in turns)
    raw_metrics = {
        "semantic_accuracy": _mean(turn["score"] for turn in turns),
        "semantic_stability": _mean(stability_scores),
        "consistency_score": _mean(
            turn["score"] for turn in turns if turn.get("consistency_checkpoint")
        ),
        "recovery_score": _mean(
            turn["score"] for turn in turns if turn.get("recovery_checkpoint")
        ),
        "context_retention": _mean(
            turn["score"] for turn in turns if turn.get("context_checkpoint")
        ),
        "long_conversation_accuracy": _mean(
            turn["score"]
            for turn in turns
            if turn.get("conversation_id") in long_conversation_ids
        ),
        "noise_resistance": _mean(
            turn["score"]
            for turn in turns
            if set(turn.get("categories") or []) & noise_categories
        ),
        "ambiguity_robustness": _mean(
            turn["score"]
            for turn in turns
            if set(turn.get("categories") or []) & ambiguity_categories
        ),
        "confidence_calibration_score": max(0.0, 1.0 - calibration_error),
    }
    robustness_score = sum(
        raw_metrics[name] * weight for name, weight in ROBUSTNESS_WEIGHTS.items()
    )
    critical_count = sum(error.get("severity") == "critical" for error in errors)
    return {
        **{name: round(value, 4) for name, value in raw_metrics.items()},
        "semantic_robustness_score": round(robustness_score, 4),
        "critical_error_count": critical_count,
        "critical_error_rate": _ratio(critical_count, len(turns)),
        "evaluated_turn_count": len(turns),
        "evaluated_conversation_count": len(conversations),
        "stability_group_count": len(stability_scores),
        "long_conversation_count": len(long_conversation_ids),
    }


def _category_results(turns: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    category_turns: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for turn in turns:
        for category in turn.get("categories") or []:
            category_turns[str(category)].append(turn)
    return {
        category: {
            "turn_count": len(items),
            "score": _mean(item["score"] for item in items),
            "error_count": sum(int(item["error_count"]) for item in items),
            "overconfident_error_count": sum(bool(item["overconfident_error"]) for item in items),
        }
        for category, items in sorted(category_turns.items())
    }


def _benchmark_comparison(
    benchmark: Mapping[str, Any],
    metrics: Mapping[str, Any],
    official_result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    official_score = None
    official_hash = None
    if official_result:
        official_score = float(
            (official_result.get("summary") or {}).get("semantic_understanding_score") or 0.0
        )
        official_hash = (official_result.get("benchmark") or {}).get("benchmark_hash")
    adversarial_score = float(metrics.get("semantic_accuracy") or 0.0)
    return {
        "official_semantic_score": official_score,
        "adversarial_semantic_score": adversarial_score,
        "adversarial_robustness_score": metrics.get("semantic_robustness_score"),
        "score_delta": (
            round(adversarial_score - official_score, 4)
            if official_score is not None
            else None
        ),
        "official_benchmark_hash": official_hash,
        "adversarial_benchmark_hash": benchmark.get("benchmark_hash"),
        "official_message_overlap_count": benchmark.get("official_message_overlap_count"),
        "official_authority": "legacy",
        "semantic_authority_mode": "shadow",
    }


def _promotion_recommendation(
    metrics: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> dict[str, Any]:
    official_score = float(comparison.get("official_semantic_score") or 0.0)
    robustness = float(metrics.get("semantic_robustness_score") or 0.0)
    context_retention = float(metrics.get("context_retention") or 0.0)
    ambiguity = float(metrics.get("ambiguity_robustness") or 0.0)
    calibration = float(metrics.get("confidence_calibration_score") or 0.0)
    critical_rate = float(metrics.get("critical_error_rate") or 0.0)
    full_gates = {
        "official_score_at_least_0_95": official_score >= 0.95,
        "robustness_at_least_0_85": robustness >= 0.85,
        "context_retention_at_least_0_85": context_retention >= 0.85,
        "ambiguity_robustness_at_least_0_85": ambiguity >= 0.85,
        "calibration_at_least_0_80": calibration >= 0.80,
        "critical_error_rate_at_most_0_02": critical_rate <= 0.02,
    }
    pilot_gates = {
        "official_score_at_least_0_95": official_score >= 0.95,
        "robustness_at_least_0_70": robustness >= 0.70,
        "context_retention_at_least_0_65": context_retention >= 0.65,
        "critical_error_rate_at_most_0_10": critical_rate <= 0.10,
    }
    if all(full_gates.values()):
        decision = "CONTROLLED_MIGRATION_READY"
        scope = "SA-3 low-risk verticals with per-turn shadow comparison and rollback"
        can_begin = True
        failed_gates: list[str] = []
    elif all(pilot_gates.values()):
        decision = "LOW_RISK_VERTICAL_PILOT_ONLY"
        scope = "One low-risk semantic consumer only; legacy remains instant rollback"
        can_begin = True
        failed_gates = [name for name, passed in full_gates.items() if not passed]
    else:
        decision = "NOT_READY_FOR_SA3"
        scope = "Remain shadow-only until failed pilot gates are resolved"
        can_begin = False
        failed_gates = [name for name, passed in pilot_gates.items() if not passed]
    return {
        "decision": decision,
        "sa3_can_begin": can_begin,
        "scope": scope,
        "failed_gates": failed_gates,
        "full_promotion_gates": full_gates,
        "pilot_gates": pilot_gates,
        "required_controls": [
            "per-turn legacy comparison",
            "instant rollback to legacy",
            "no broad authority promotion",
            "critical semantic errors block promotion",
        ],
        "rationale": [
            f"Official benchmark score: {official_score:.2%}",
            f"Adversarial robustness score: {robustness:.2%}",
            f"Context retention: {context_retention:.2%}",
            f"Critical error rate: {critical_rate:.2%}",
        ],
    }


def _frequent_errors(errors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(
        (
            str(error.get("classification") or ""),
            str(error.get("difference") or ""),
            str(error.get("field") or ""),
        )
        for error in errors
    )
    return [
        {
            "classification": classification,
            "difference": difference,
            "field": field_name,
            "count": count,
        }
        for (classification, difference, field_name), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]


def _metric_bands(
    metrics: Mapping[str, Any],
    *,
    minimum: float,
    keep_above: bool,
) -> list[dict[str, Any]]:
    ignored = {
        "critical_error_count",
        "critical_error_rate",
        "evaluated_turn_count",
        "evaluated_conversation_count",
        "stability_group_count",
        "long_conversation_count",
    }
    values = [
        (name, float(value))
        for name, value in metrics.items()
        if name not in ignored and isinstance(value, (int, float))
    ]
    selected = [
        (name, value)
        for name, value in values
        if (value >= minimum if keep_above else value < minimum)
    ]
    return [
        {"metric": name, "score": round(value, 4)}
        for name, value in sorted(selected, key=lambda item: (-item[1], item[0]))
    ]


def _mean(values: Iterable[float | int]) -> float:
    collected = [float(value) for value in values]
    return round(fmean(collected), 4) if collected else 0.0


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def render_adversarial_semantic_report(result: Mapping[str, Any]) -> str:
    benchmark = result["benchmark"]
    metrics = result["metrics"]
    comparison = result["benchmark_comparison"]
    calibration = result["confidence_calibration"]
    recommendation = result["recommendation"]
    lines = [
        "# Semantic Authority Adversarial Validation",
        "",
        "## Corpus",
        "",
        f"- Conversations: {benchmark['conversation_count']}",
        f"- Turns: {benchmark['turn_count']}",
        f"- Official overlap: {benchmark['official_message_overlap_count']}",
        f"- Messages over 2,000 words: {benchmark['long_message_count']}",
        f"- Conversations over 50 turns: {benchmark['stress_conversation_count']}",
        f"- Benchmark hash: `{benchmark['benchmark_hash']}`",
        "",
        "## Official vs Adversarial",
        "",
        "| Metric | Score |",
        "| --- | ---: |",
        f"| Official semantic understanding | {_percent(comparison.get('official_semantic_score'))} |",
        f"| Adversarial semantic accuracy | {_percent(comparison.get('adversarial_semantic_score'))} |",
        f"| Adversarial robustness | {_percent(comparison.get('adversarial_robustness_score'))} |",
        f"| Delta | {_percent(comparison.get('score_delta'))} |",
        "",
        "## Robustness",
        "",
        "| Metric | Score |",
        "| --- | ---: |",
    ]
    for name in ROBUSTNESS_WEIGHTS:
        lines.append(f"| {name.replace('_', ' ').title()} | {_percent(metrics.get(name))} |")
    lines.extend(
        [
            f"| Semantic Robustness Score | {_percent(metrics.get('semantic_robustness_score'))} |",
            f"| Critical Error Rate | {_percent(metrics.get('critical_error_rate'))} |",
            "",
            "## Confidence Calibration",
            "",
            f"- Mean confidence: {_percent(calibration.get('mean_confidence'))}",
            f"- Mean turn score: {_percent(calibration.get('mean_turn_score'))}",
            f"- Mean absolute calibration error: {_percent(calibration.get('mean_absolute_calibration_error'))}",
            f"- Overconfident error rate: {_percent(calibration.get('overconfident_error_rate'))}",
            "",
            "## Error Classification",
            "",
            "| Classification | Count |",
            "| --- | ---: |",
        ]
    )
    for name, count in result["error_classification"]["counts"].items():
        lines.append(f"| {name} | {count} |")
    lines.extend(
        [
            "",
            "## Category Results",
            "",
            "| Category | Turns | Score | Errors |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for name, category in result["categories"].items():
        lines.append(
            f"| {name} | {category['turn_count']} | {_percent(category['score'])} | {category['error_count']} |"
        )
    lines.extend(
        [
            "",
            "## Worst Conversations",
            "",
            "| Rank | Conversation | Profile | Turns | Score | Errors |",
            "| ---: | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for item in result["worst_cases"]:
        lines.append(
            f"| {item['rank']} | {item['conversation_id']} | {item['profile']} | {item['turn_count']} | {_percent(item['score'])} | {item['error_count']} |"
        )
    lines.extend(
        [
            "",
            "## Promotion Recommendation",
            "",
            f"**{recommendation['decision']}**",
            "",
            recommendation["scope"],
            "",
            *[f"- {line}" for line in recommendation["rationale"]],
            "",
            "Legacy remains the only effective authority. This evaluation called SemanticAuthority directly and did not invoke Runtime, mutate state, or influence visible decisions.",
            "",
        ]
    )
    return "\n".join(lines)


def _percent(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}"
