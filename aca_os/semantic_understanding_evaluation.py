from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from aca_core.text import normalize_text
from aca_kernel.core.events import Event
from aca_os.semantic_authority import SEMANTIC_AUTHORITY_VERSION, SemanticAuthority


DEFAULT_SEMANTIC_UNDERSTANDING_BENCHMARK = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "semantic"
    / "aca_semantic_understanding_benchmark_v1.json"
)

SET_METRICS = {
    "entities": ("entity_recall", "entity_precision"),
    "facts": ("fact_recall", "fact_precision"),
    "goals": ("goal_recall", "goal_precision"),
    "topics": ("topic_recall", "topic_precision"),
    "events": ("event_recall", "event_precision"),
}
ACCURACY_METRICS = (
    "intent_agreement",
    "negation_accuracy",
    "correction_accuracy",
    "retraction_accuracy",
    "coreference_accuracy",
    "temporal_accuracy",
    "ambiguity_detection_accuracy",
    "contradiction_accuracy",
    "conversational_act_accuracy",
    "goal_priority_accuracy",
)
REQUIRED_DASHBOARD_METRICS = (
    "entity_recall",
    "entity_precision",
    "fact_recall",
    "fact_precision",
    "goal_recall",
    "goal_precision",
    "topic_recall",
    "topic_precision",
    "intent_agreement",
    "negation_accuracy",
    "correction_accuracy",
    "retraction_accuracy",
    "coreference_accuracy",
    "temporal_accuracy",
    "ambiguity_detection_accuracy",
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


@dataclass
class SemanticEvaluationContext:
    """Gold prior context used only to isolate each turn during evaluation."""

    conversation_id: str
    turn_count: int = 0
    confirmed_facts: dict[str, Any] = field(default_factory=dict)
    topic_stack: list[dict[str, Any]] = field(default_factory=list)
    pending_questions: list[dict[str, Any]] = field(default_factory=list)
    relevant_context: dict[str, Any] = field(default_factory=dict)
    active_mission: dict[str, Any] | None = None


@dataclass
class MetricAccumulator:
    sets: dict[str, dict[str, int]] = field(default_factory=dict)
    accuracies: dict[str, dict[str, int]] = field(default_factory=dict)

    def add_set(self, name: str, *, true_positive: int, expected: int, actual: int) -> None:
        counter = self.sets.setdefault(name, {"true_positive": 0, "expected": 0, "actual": 0})
        counter["true_positive"] += int(true_positive)
        counter["expected"] += int(expected)
        counter["actual"] += int(actual)

    def add_accuracy(self, name: str, *, correct: bool) -> None:
        counter = self.accuracies.setdefault(name, {"correct": 0, "total": 0})
        counter["correct"] += int(bool(correct))
        counter["total"] += 1

    def merge(self, other: "MetricAccumulator") -> None:
        for name, counter in other.sets.items():
            self.add_set(
                name,
                true_positive=counter["true_positive"],
                expected=counter["expected"],
                actual=counter["actual"],
            )
        for name, counter in other.accuracies.items():
            target = self.accuracies.setdefault(name, {"correct": 0, "total": 0})
            target["correct"] += counter["correct"]
            target["total"] += counter["total"]

    def summary(self) -> dict[str, Any]:
        metrics: dict[str, float | None] = {}
        details: dict[str, Any] = {}
        for source_name, (recall_name, precision_name) in SET_METRICS.items():
            counter = self.sets.get(source_name, {"true_positive": 0, "expected": 0, "actual": 0})
            recall = _ratio(counter["true_positive"], counter["expected"])
            precision = _ratio(counter["true_positive"], counter["actual"])
            metrics[recall_name] = recall
            metrics[precision_name] = precision
            details[source_name] = dict(counter)
        for name in ACCURACY_METRICS:
            counter = self.accuracies.get(name, {"correct": 0, "total": 0})
            metrics[name] = _ratio(counter["correct"], counter["total"])
            details[name] = dict(counter)
        available = [float(value) for value in metrics.values() if value is not None]
        score = round(sum(available) / len(available), 4) if available else None
        return {
            "semantic_understanding_score": score,
            "metrics": metrics,
            "metric_percentages": {
                name: round(float(value) * 100, 2) if value is not None else None
                for name, value in metrics.items()
            },
            "metric_details": details,
        }


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def load_semantic_understanding_benchmark(
    path: str | Path | None = None,
) -> dict[str, Any]:
    benchmark_path = Path(path) if path else DEFAULT_SEMANTIC_UNDERSTANDING_BENCHMARK
    manifest = json.loads(benchmark_path.read_text(encoding="utf-8"))
    conversations = _expand_profiles(manifest.get("profiles") or [])
    messages = [turn["message"] for conversation in conversations for turn in conversation["turns"]]
    if len(messages) != len(set(messages)):
        duplicates = [message for message, count in Counter(messages).items() if count > 1]
        raise ValueError(f"Semantic benchmark contains duplicate messages: {duplicates[:5]}")
    expanded = {
        "contract": manifest.get("contract"),
        "version": manifest.get("version"),
        "name": manifest.get("name"),
        "methodology": manifest.get("methodology"),
        "context_policy": manifest.get("context_policy"),
        "description": manifest.get("description"),
        "profile_count": len(manifest.get("profiles") or []),
        "conversation_count": len(conversations),
        "turn_count": len(messages),
        "unique_message_count": len(set(messages)),
        "conversations": conversations,
    }
    expanded["benchmark_hash"] = _sha256(expanded)
    return expanded


def _expand_profiles(profiles: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    conversations: list[dict[str, Any]] = []
    for profile in profiles:
        profile_id = str(profile.get("id") or "profile")
        profile_categories = list(profile.get("categories") or [])
        templates = list(profile.get("turns") or [])
        for index, variant in enumerate(profile.get("variants") or [], start=1):
            values = _SafeFormatDict({str(key): value for key, value in dict(variant).items()})
            turns = []
            for turn_number, template in enumerate(templates, start=1):
                turn = _format_recursive(deepcopy(template), values)
                turns.append(
                    {
                        "turn": turn_number,
                        "message": turn["message"],
                        "categories": _unique(profile_categories + list(turn.get("categories") or [])),
                        "expected": dict(turn.get("expected") or {}),
                    }
                )
            conversations.append(
                {
                    "id": f"{profile_id}:{index:02d}",
                    "profile": profile_id,
                    "variant": index,
                    "categories": profile_categories,
                    "turns": turns,
                }
            )
    return conversations


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        raise KeyError(f"Missing benchmark template value: {key}")


def _format_recursive(value: Any, values: Mapping[str, Any]) -> Any:
    if isinstance(value, str):
        return value.format_map(values)
    if isinstance(value, list):
        return [_format_recursive(item, values) for item in value]
    if isinstance(value, dict):
        return {str(key): _format_recursive(item, values) for key, item in value.items()}
    return value


def _unique(values: Sequence[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value not in output:
            output.append(value)
    return output


def run_semantic_understanding_evaluation(
    *,
    conversation_ids: Iterable[str] | None = None,
    profile_ids: Iterable[str] | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    benchmark = load_semantic_understanding_benchmark(path)
    selected_conversations = set(conversation_ids or [])
    selected_profiles = set(profile_ids or [])
    conversations = [
        conversation
        for conversation in benchmark["conversations"]
        if (not selected_conversations or conversation["id"] in selected_conversations)
        and (not selected_profiles or conversation["profile"] in selected_profiles)
    ]
    authority = SemanticAuthority()
    overall = MetricAccumulator()
    categories: dict[str, MetricAccumulator] = {}
    conversation_results = []
    all_errors: list[dict[str, Any]] = []

    for conversation in conversations:
        context = SemanticEvaluationContext(conversation_id=conversation["id"])
        conversation_accumulator = MetricAccumulator()
        turn_results = []
        for turn in conversation["turns"]:
            event = Event(
                type="user_message",
                payload=turn["message"],
                metadata={"conversation_id": conversation["id"]},
            )
            representation = authority.interpret(
                event,
                conversation_state=context,
                turn_number=turn["turn"],
            )
            actual = _observable_semantics(representation.to_dict())
            turn_accumulator, errors, checks = _evaluate_turn(
                expected=turn["expected"],
                actual=actual,
                conversation_id=conversation["id"],
                turn_number=turn["turn"],
                message=turn["message"],
                categories=turn["categories"],
            )
            overall.merge(turn_accumulator)
            conversation_accumulator.merge(turn_accumulator)
            for category in turn["categories"]:
                categories.setdefault(category, MetricAccumulator()).merge(turn_accumulator)
            all_errors.extend(errors)
            turn_summary = turn_accumulator.summary()
            turn_results.append(
                {
                    "turn": turn["turn"],
                    "message": turn["message"],
                    "categories": list(turn["categories"]),
                    "expected": deepcopy(turn["expected"]),
                    "actual": actual,
                    "checks": checks,
                    "metrics": turn_summary["metrics"],
                    "semantic_understanding_score": turn_summary["semantic_understanding_score"],
                    "errors": errors,
                }
            )
            _advance_gold_context(context, turn["expected"], turn["turn"])
        conversation_summary = conversation_accumulator.summary()
        conversation_results.append(
            {
                "id": conversation["id"],
                "profile": conversation["profile"],
                "categories": list(conversation["categories"]),
                "turn_count": len(turn_results),
                "semantic_understanding_score": conversation_summary["semantic_understanding_score"],
                "metrics": conversation_summary["metrics"],
                "error_count": sum(len(turn["errors"]) for turn in turn_results),
                "turns": turn_results,
            }
        )

    summary = overall.summary()
    category_results = {
        name: {
            **accumulator.summary(),
            "turn_count": sum(
                1
                for conversation in conversation_results
                for turn in conversation["turns"]
                if name in turn["categories"]
            ),
            "error_count": sum(1 for error in all_errors if name in error["categories"]),
        }
        for name, accumulator in sorted(categories.items())
    }
    errors_by_metric = Counter(error["metric"] for error in all_errors)
    errors_by_severity = Counter(error["severity"] for error in all_errors)
    frequent_errors = _frequent_errors(all_errors)
    result = {
        "contract": "semantic_understanding_evaluation_result.v1",
        "benchmark": {
            "contract": benchmark["contract"],
            "version": benchmark["version"],
            "benchmark_hash": benchmark["benchmark_hash"],
            "methodology": benchmark["methodology"],
            "context_policy": benchmark["context_policy"],
            "profile_count": len({conversation["profile"] for conversation in conversations}),
            "conversation_count": len(conversations),
            "turn_count": sum(len(conversation["turns"]) for conversation in conversations),
            "unique_message_count": len(
                {
                    turn["message"]
                    for conversation in conversations
                    for turn in conversation["turns"]
                }
            ),
        },
        "engine": {
            "component": "semantic_authority",
            "version": SEMANTIC_AUTHORITY_VERSION,
            "mode": "shadow",
            "runtime_used": False,
            "decision_influence": False,
            "state_mutation": False,
        },
        "summary": summary,
        "dashboard": _dashboard(summary),
        "categories": category_results,
        "conversations": conversation_results,
        "errors": all_errors,
        "frequent_errors": frequent_errors,
        "distribution": {
            "errors_by_metric": dict(sorted(errors_by_metric.items())),
            "errors_by_severity": dict(sorted(errors_by_severity.items())),
            "turn_score_buckets": _score_distribution(conversation_results),
            "total_errors": len(all_errors),
        },
        "reproducibility": {
            "deterministic": True,
            "provider_calls": 0,
            "runtime_calls": 0,
            "benchmark_hash": benchmark["benchmark_hash"],
        },
    }
    result["report_hash"] = _sha256(result)
    return result


def _observable_semantics(representation: Mapping[str, Any]) -> dict[str, Any]:
    intents = sorted(
        [dict(item) for item in representation.get("intents") or []],
        key=lambda item: (
            int(item.get("priority") or 999),
            -float(item.get("confidence") or 0.0),
            str(item.get("type") or ""),
        ),
    )
    entities = [
        {
            "type": item.get("type"),
            "value": item.get("value"),
            "role": item.get("role"),
        }
        for item in representation.get("entities") or []
    ]
    facts = [
        {
            "predicate": item.get("predicate"),
            "value": item.get("value"),
            "polarity": item.get("polarity"),
            "modality": item.get("modality"),
        }
        for item in representation.get("assertions") or []
        if item.get("predicate") not in {"user_statement", "user_question"}
    ]
    goals = [
        {"type": item.get("type"), "target": item.get("target")}
        for item in representation.get("goals") or []
    ]
    topics = [str(item.get("type") or "") for item in (representation.get("topic_structure") or {}).get("topics") or []]
    events = [{"type": item.get("type"), "status": item.get("status")} for item in representation.get("events") or []]
    corrections = [str(item.get("operation") or "") for item in representation.get("corrections") or []]
    temporal = [
        str(item.get("value") or "")
        for item in representation.get("entities") or []
        if item.get("type") == "temporal_expression"
    ]
    grounding = representation.get("grounding") or {}
    coreferences = [
        {
            "mention": item.get("mention"),
            "target_type": item.get("target_type"),
            "target_value": item.get("target_value"),
        }
        for item in grounding.get("resolved_coreferences") or []
        if isinstance(item, Mapping)
    ]
    ambiguity = bool(representation.get("uncertainty")) or any(
        item.get("operation") == "replace_prior_assertion" and not item.get("target")
        for item in representation.get("corrections") or []
    )
    return {
        "language": representation.get("language"),
        "conversational_act": (representation.get("conversational_act") or {}).get("act"),
        "entities": entities,
        "facts": facts,
        "events": events,
        "goals": goals,
        "topics": topics,
        "intents": [str(item.get("type") or "") for item in intents],
        "primary_intent": str((intents[0] if intents else {}).get("type") or ""),
        "negations": [
            {"predicate": item["predicate"], "value": item["value"]}
            for item in facts
            if item.get("value") is False or item.get("polarity") == "negative"
        ],
        "corrections": corrections,
        "retractions": [item for item in corrections if item == "retract"],
        "coreferences": coreferences,
        "temporal": temporal,
        "ambiguity": ambiguity,
        "contradictions": [
            {
                "fact": item.get("fact"),
                "previous_value": item.get("previous_value"),
                "new_value": item.get("new_value"),
            }
            for item in representation.get("contradictions") or []
        ],
    }


def _evaluate_turn(
    *,
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    conversation_id: str,
    turn_number: int,
    message: str,
    categories: Sequence[str],
) -> tuple[MetricAccumulator, list[dict[str, Any]], list[dict[str, Any]]]:
    accumulator = MetricAccumulator()
    errors: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    for source_name in SET_METRICS:
        if source_name not in expected:
            continue
        expected_items = list(expected.get(source_name) or [])
        actual_items = list(actual.get(source_name) or [])
        matched_expected, matched_actual = _match_items(source_name, expected_items, actual_items)
        accumulator.add_set(
            source_name,
            true_positive=len(matched_expected),
            expected=len(expected_items),
            actual=len(actual_items),
        )
        checks.append(
            {
                "metric": source_name,
                "expected_count": len(expected_items),
                "actual_count": len(actual_items),
                "matched_count": len(matched_expected),
                "passed": len(matched_expected) == len(expected_items) and len(matched_actual) == len(actual_items),
            }
        )
        for index, item in enumerate(expected_items):
            if index in matched_expected:
                continue
            errors.append(
                _error(
                    metric=SET_METRICS[source_name][0],
                    category=source_name,
                    severity=_missing_severity(source_name, categories),
                    expected=item,
                    actual=actual_items,
                    difference="missing_expected_semantic_item",
                    conversation_id=conversation_id,
                    turn_number=turn_number,
                    message=message,
                    categories=categories,
                )
            )
        for index, item in enumerate(actual_items):
            if index in matched_actual:
                continue
            errors.append(
                _error(
                    metric=SET_METRICS[source_name][1],
                    category=source_name,
                    severity="low",
                    expected=expected_items,
                    actual=item,
                    difference="unexpected_semantic_item",
                    conversation_id=conversation_id,
                    turn_number=turn_number,
                    message=message,
                    categories=categories,
                )
            )

    if "primary_intent" in expected or "intents" in expected:
        expected_intent = str(expected.get("primary_intent") or (expected.get("intents") or [""])[0])
        actual_intent = str(actual.get("primary_intent") or "")
        _accuracy_check(
            accumulator,
            errors,
            checks,
            metric="intent_agreement",
            expected=expected_intent,
            actual=actual_intent,
            category="intents",
            severity="medium",
            conversation_id=conversation_id,
            turn_number=turn_number,
            message=message,
            categories=categories,
        )
    for expected_key, actual_key, metric, severity in (
        ("negations", "negations", "negation_accuracy", "high"),
        ("corrections", "corrections", "correction_accuracy", "high"),
        ("retractions", "retractions", "retraction_accuracy", "high"),
        ("coreferences", "coreferences", "coreference_accuracy", "medium"),
        ("temporal", "temporal", "temporal_accuracy", "medium"),
        ("contradictions", "contradictions", "contradiction_accuracy", "high"),
    ):
        if expected_key not in expected:
            continue
        expected_value = expected.get(expected_key) or []
        actual_value = actual.get(actual_key) or []
        correct = _contains_all(expected_key, expected_value, actual_value)
        _accuracy_check(
            accumulator,
            errors,
            checks,
            metric=metric,
            expected=expected_value,
            actual=actual_value,
            category=expected_key,
            severity=severity,
            conversation_id=conversation_id,
            turn_number=turn_number,
            message=message,
            categories=categories,
            explicit_correct=correct,
        )
    if "ambiguity" in expected:
        _accuracy_check(
            accumulator,
            errors,
            checks,
            metric="ambiguity_detection_accuracy",
            expected=bool(expected["ambiguity"]),
            actual=bool(actual.get("ambiguity")),
            category="ambiguity",
            severity="medium",
            conversation_id=conversation_id,
            turn_number=turn_number,
            message=message,
            categories=categories,
        )
    if "conversational_act" in expected:
        _accuracy_check(
            accumulator,
            errors,
            checks,
            metric="conversational_act_accuracy",
            expected=expected["conversational_act"],
            actual=actual.get("conversational_act"),
            category="conversational_act",
            severity="medium",
            conversation_id=conversation_id,
            turn_number=turn_number,
            message=message,
            categories=categories,
        )
    if "primary_goal_contains" in expected:
        target = normalize_text(expected["primary_goal_contains"])
        actual_targets = [normalize_text(item.get("target") or "") for item in actual.get("goals") or []]
        correct = any(target and target in value for value in actual_targets)
        _accuracy_check(
            accumulator,
            errors,
            checks,
            metric="goal_priority_accuracy",
            expected=expected["primary_goal_contains"],
            actual=[item.get("target") for item in actual.get("goals") or []],
            category="goal_priority",
            severity="medium",
            conversation_id=conversation_id,
            turn_number=turn_number,
            message=message,
            categories=categories,
            explicit_correct=correct,
        )
    return accumulator, errors, checks


def _match_items(
    source_name: str,
    expected: Sequence[Any],
    actual: Sequence[Any],
) -> tuple[set[int], set[int]]:
    matched_expected: set[int] = set()
    matched_actual: set[int] = set()
    for expected_index, expected_item in enumerate(expected):
        for actual_index, actual_item in enumerate(actual):
            if actual_index in matched_actual:
                continue
            if _item_matches(source_name, expected_item, actual_item):
                matched_expected.add(expected_index)
                matched_actual.add(actual_index)
                break
    return matched_expected, matched_actual


def _item_matches(source_name: str, expected: Any, actual: Any) -> bool:
    if source_name == "topics":
        return normalize_text(expected) == normalize_text(actual)
    if not isinstance(expected, Mapping) or not isinstance(actual, Mapping):
        return _normalized_value(expected) == _normalized_value(actual)
    if source_name == "entities":
        keys = ("type", "value", "role")
    elif source_name == "facts":
        keys = ("predicate", "value")
    elif source_name == "goals":
        keys = ("type", "target")
    elif source_name == "events":
        keys = ("type", "status")
    else:
        keys = tuple(expected)
    for key in keys:
        if key not in expected:
            continue
        if _normalized_value(expected.get(key)) != _normalized_value(actual.get(key)):
            return False
    return True


def _normalized_value(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_text(value)
    if isinstance(value, list):
        return [_normalized_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalized_value(item) for key, item in sorted(value.items())}
    return value


def _contains_all(name: str, expected: Sequence[Any], actual: Sequence[Any]) -> bool:
    if name in {"negations", "coreferences", "contradictions"}:
        matched, _ = _match_items_for_accuracy(expected, actual)
        return len(matched) == len(expected)
    expected_normalized = {_canonical_json(_normalized_value(item)) for item in expected}
    actual_normalized = {_canonical_json(_normalized_value(item)) for item in actual}
    return expected_normalized <= actual_normalized


def _match_items_for_accuracy(
    expected: Sequence[Any], actual: Sequence[Any]
) -> tuple[set[int], set[int]]:
    matched_expected: set[int] = set()
    matched_actual: set[int] = set()
    for expected_index, expected_item in enumerate(expected):
        for actual_index, actual_item in enumerate(actual):
            if actual_index in matched_actual:
                continue
            if not isinstance(expected_item, Mapping) or not isinstance(actual_item, Mapping):
                matches = _normalized_value(expected_item) == _normalized_value(actual_item)
            else:
                matches = all(
                    _normalized_value(value) == _normalized_value(actual_item.get(key))
                    for key, value in expected_item.items()
                )
            if matches:
                matched_expected.add(expected_index)
                matched_actual.add(actual_index)
                break
    return matched_expected, matched_actual


def _accuracy_check(
    accumulator: MetricAccumulator,
    errors: list[dict[str, Any]],
    checks: list[dict[str, Any]],
    *,
    metric: str,
    expected: Any,
    actual: Any,
    category: str,
    severity: str,
    conversation_id: str,
    turn_number: int,
    message: str,
    categories: Sequence[str],
    explicit_correct: bool | None = None,
) -> None:
    correct = explicit_correct if explicit_correct is not None else _normalized_value(expected) == _normalized_value(actual)
    accumulator.add_accuracy(metric, correct=correct)
    checks.append(
        {
            "metric": metric,
            "expected": deepcopy(expected),
            "actual": deepcopy(actual),
            "passed": bool(correct),
        }
    )
    if not correct:
        errors.append(
            _error(
                metric=metric,
                category=category,
                severity=severity,
                expected=expected,
                actual=actual,
                difference="incorrect_or_missing_semantic_result",
                conversation_id=conversation_id,
                turn_number=turn_number,
                message=message,
                categories=categories,
            )
        )


def _error(
    *,
    metric: str,
    category: str,
    severity: str,
    expected: Any,
    actual: Any,
    difference: str,
    conversation_id: str,
    turn_number: int,
    message: str,
    categories: Sequence[str],
) -> dict[str, Any]:
    return {
        "error_id": f"{conversation_id}:turn-{turn_number}:{metric}:{difference}",
        "conversation_id": conversation_id,
        "turn": turn_number,
        "message": message,
        "metric": metric,
        "category": category,
        "categories": list(categories),
        "severity": severity,
        "expected": deepcopy(expected),
        "actual": deepcopy(actual),
        "difference": difference,
    }


def _missing_severity(source_name: str, categories: Sequence[str]) -> str:
    if source_name == "facts" and any(
        category in categories
        for category in ("negative_fact", "negation", "contradiction", "conditional_fact")
    ):
        return "high"
    if source_name in {"goals", "topics"}:
        return "medium"
    return "medium"


def _advance_gold_context(
    context: SemanticEvaluationContext,
    expected: Mapping[str, Any],
    turn_number: int,
) -> None:
    for fact in expected.get("facts") or []:
        predicate = str(fact.get("predicate") or "")
        if not predicate:
            continue
        context.confirmed_facts[predicate] = {
            "contract": "conversational_fact.v1",
            "type": predicate,
            "value": deepcopy(fact.get("value")),
            "status": "active",
            "origin": "semantic_evaluation_gold",
            "confidence": 1.0,
        }
    for entity in expected.get("entities") or []:
        key = f"entity:{entity.get('type')}:{normalize_text(entity.get('value') or '')}"
        context.relevant_context[key] = deepcopy(entity)
    topics = expected.get("topics") or []
    if topics:
        context.topic_stack = [
            {
                "id": f"gold-topic:{topic}",
                "topic_id": f"gold-topic:{topic}",
                "type": topic,
                "status": "active" if index == 0 else "suspended",
            }
            for index, topic in enumerate(topics)
        ]
    context.turn_count = turn_number


def _dashboard(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    metrics = summary.get("metrics") or {}
    labels = {
        "entity_recall": "Entity Recall",
        "entity_precision": "Entity Precision",
        "fact_recall": "Fact Recall",
        "fact_precision": "Fact Precision",
        "goal_recall": "Goal Recall",
        "goal_precision": "Goal Precision",
        "topic_recall": "Topic Recall",
        "topic_precision": "Topic Precision",
        "intent_agreement": "Intent Agreement",
        "negation_accuracy": "Negation",
        "correction_accuracy": "Corrections",
        "retraction_accuracy": "Retractions",
        "coreference_accuracy": "Coreference",
        "temporal_accuracy": "Temporal",
        "ambiguity_detection_accuracy": "Ambiguity Detection",
    }
    return [
        {
            "metric": name,
            "label": labels[name],
            "score": metrics.get(name),
            "percentage": round(float(metrics[name]) * 100, 2) if metrics.get(name) is not None else None,
        }
        for name in REQUIRED_DASHBOARD_METRICS
    ]


def _frequent_errors(errors: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    counter = Counter(
        (
            str(error.get("metric")),
            str(error.get("difference")),
            _expected_signature(error.get("expected")),
        )
        for error in errors
    )
    return [
        {
            "metric": metric,
            "difference": difference,
            "expected_signature": signature,
            "count": count,
        }
        for (metric, difference, signature), count in sorted(
            counter.items(), key=lambda item: (-item[1], item[0])
        )[:50]
    ]


def _expected_signature(value: Any) -> str:
    if isinstance(value, Mapping):
        return str(
            value.get("type")
            or value.get("predicate")
            or value.get("mention")
            or value.get("fact")
            or "mapping"
        )
    if isinstance(value, list):
        return "list"
    return str(value)


def _score_distribution(conversations: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    buckets = {"0-24": 0, "25-49": 0, "50-74": 0, "75-89": 0, "90-100": 0, "not_scored": 0}
    for conversation in conversations:
        for turn in conversation.get("turns") or []:
            score = turn.get("semantic_understanding_score")
            if score is None:
                buckets["not_scored"] += 1
                continue
            percentage = float(score) * 100
            if percentage < 25:
                buckets["0-24"] += 1
            elif percentage < 50:
                buckets["25-49"] += 1
            elif percentage < 75:
                buckets["50-74"] += 1
            elif percentage < 90:
                buckets["75-89"] += 1
            else:
                buckets["90-100"] += 1
    return buckets


def render_semantic_understanding_report(result: Mapping[str, Any]) -> str:
    benchmark = result.get("benchmark") or {}
    summary = result.get("summary") or {}
    lines = [
        "# ACA Semantic Understanding Evaluation",
        "",
        f"- Benchmark: `{benchmark.get('contract')}`",
        f"- Conversations: `{benchmark.get('conversation_count')}`",
        f"- Turns: `{benchmark.get('turn_count')}`",
        f"- Unique messages: `{benchmark.get('unique_message_count')}`",
        f"- SemanticAuthority mode: `{(result.get('engine') or {}).get('mode')}`",
        f"- Runtime used: `{str(bool((result.get('engine') or {}).get('runtime_used'))).lower()}`",
        f"- Report hash: `{result.get('report_hash')}`",
        "",
        "## Dashboard",
        "",
        "| Metric | Score |",
        "| --- | ---: |",
    ]
    for item in result.get("dashboard") or []:
        value = "n/a" if item.get("percentage") is None else f"{item['percentage']:.2f}%"
        lines.append(f"| {item['label']} | {value} |")
    lines.extend(
        [
            "",
            f"**Semantic Understanding Score:** {_format_percentage(summary.get('semantic_understanding_score'))}",
            "",
            "## Results By Category",
            "",
            "| Category | Turns | Score | Errors |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for name, category in (result.get("categories") or {}).items():
        lines.append(
            f"| {name} | {category.get('turn_count', 0)} | "
            f"{_format_percentage(category.get('semantic_understanding_score'))} | "
            f"{category.get('error_count', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Results By Conversation",
            "",
            "| Conversation | Profile | Score | Errors |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for conversation in result.get("conversations") or []:
        lines.append(
            f"| {conversation['id']} | {conversation['profile']} | "
            f"{_format_percentage(conversation.get('semantic_understanding_score'))} | "
            f"{conversation.get('error_count', 0)} |"
        )
    lines.extend(
        [
            "",
            "## Results By Turn",
            "",
            "| Conversation | Turn | Score | Errors | Message |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for conversation in result.get("conversations") or []:
        for turn in conversation.get("turns") or []:
            message = str(turn.get("message") or "").replace("|", "\\|")
            lines.append(
                f"| {conversation['id']} | {turn['turn']} | "
                f"{_format_percentage(turn.get('semantic_understanding_score'))} | "
                f"{len(turn.get('errors') or [])} | {message} |"
            )
    lines.extend(
        [
            "",
            "## Frequent Errors",
            "",
            "| Metric | Difference | Expected | Count |",
            "| --- | --- | --- | ---: |",
        ]
    )
    for error in result.get("frequent_errors") or []:
        lines.append(
            f"| {error['metric']} | {error['difference']} | "
            f"{error['expected_signature']} | {error['count']} |"
        )
    lines.extend(
        [
            "",
            "## Error Distribution",
            "",
            f"- Total errors: `{(result.get('distribution') or {}).get('total_errors', 0)}`",
            f"- By severity: `{json.dumps((result.get('distribution') or {}).get('errors_by_severity', {}), ensure_ascii=False, sort_keys=True)}`",
            f"- By metric: `{json.dumps((result.get('distribution') or {}).get('errors_by_metric', {}), ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Methodology",
            "",
            "SemanticAuthority is executed directly. ACAOSRuntime is never instantiated. "
            "Prior context is teacher-forced from gold annotations to isolate turn-level understanding. "
            "No metric can affect a Runtime decision or user-visible response.",
        ]
    )
    return "\n".join(lines) + "\n"


def _format_percentage(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.2f}%"
