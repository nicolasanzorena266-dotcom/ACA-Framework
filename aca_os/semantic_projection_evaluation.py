from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from aca_kernel.core.events import Event
from aca_os.semantic_projection import PROJECTION_NAMES
from sdk.factory import build_galicia_runtime


DEFAULT_SEMANTIC_PROJECTION_BENCHMARK = (
    Path(__file__).resolve().parents[1]
    / "benchmarks"
    / "semantic"
    / "aca_semantic_projection_shadow_benchmark_v1.json"
)


def load_semantic_projection_benchmark(
    path: str | Path | None = None,
) -> dict[str, Any]:
    benchmark_path = Path(path) if path else DEFAULT_SEMANTIC_PROJECTION_BENCHMARK
    return json.loads(benchmark_path.read_text(encoding="utf-8"))


def run_semantic_projection_benchmark(
    *,
    scenario_ids: Iterable[str] | None = None,
    path: str | Path | None = None,
) -> dict[str, Any]:
    suite = load_semantic_projection_benchmark(path)
    selected = set(scenario_ids or [])
    scenarios = [
        scenario
        for scenario in suite.get("scenarios") or []
        if not selected or scenario.get("id") in selected
    ]
    results = []
    all_turns = []
    status_counts: Counter[str] = Counter()
    metric_values: dict[str, list[float]] = {}
    observation_failures = []
    authority_violations = []

    for scenario in scenarios:
        runtime = build_galicia_runtime()
        conversation_id = f"semantic-projection-benchmark:{scenario['id']}"
        turn_results = []
        for turn_number, turn in enumerate(scenario.get("turns") or [], start=1):
            state = runtime.process(
                Event(
                    type="user_message",
                    payload=str(turn.get("user") or ""),
                    metadata={"conversation_id": conversation_id},
                )
            )
            runtime_record = state.facts.get("conversation_state_runtime", {})
            shadow = runtime_record.get("semantic_projection_shadow", {})
            projection = shadow.get("semantic_projection", {})
            comparison = shadow.get("comparison", {})
            checks = _evaluate_observations(turn.get("expect") or {}, projection)
            failures = [check for check in checks if not check["passed"]]
            if failures:
                observation_failures.append(
                    {
                        "scenario_id": scenario["id"],
                        "turn": turn_number,
                        "failures": failures,
                    }
                )
            if (
                shadow.get("authority_mode") != "legacy"
                or shadow.get("semantic_authority_mode") != "shadow"
                or shadow.get("decision_influence") is not False
                or shadow.get("state_mutation") is not False
            ):
                authority_violations.append(
                    {"scenario_id": scenario["id"], "turn": turn_number}
                )
            for item in (shadow.get("projection_diff") or {}).values():
                status_counts[str(item.get("status") or "UNKNOWN")] += 1
            for name, value in (shadow.get("metrics") or {}).items():
                metric_values.setdefault(str(name), []).append(float(value or 0.0))

            turn_result = {
                "turn": turn_number,
                "user": turn.get("user"),
                "visible_response": state.response,
                "authority_mode": shadow.get("authority_mode"),
                "semantic_authority_mode": shadow.get("semantic_authority_mode"),
                "semantic_representation_id": shadow.get("semantic_representation_id"),
                "semantic_projection_id": shadow.get("semantic_projection_id"),
                "semantic_projection_hash": shadow.get("semantic_projection_hash"),
                "comparison_hash": comparison.get("projection_hash"),
                "legacy_projection": shadow.get("legacy_projection", {}),
                "semantic_projection": projection,
                "projection_diff": shadow.get("projection_diff", {}),
                "field_diff": shadow.get("field_diff", []),
                "metrics": shadow.get("metrics", {}),
                "observation_checks": checks,
                "complete": _complete_shadow_artifact(shadow),
                "decision_influence": shadow.get("decision_influence"),
                "state_mutation": shadow.get("state_mutation"),
            }
            turn_results.append(turn_result)
            all_turns.append(turn_result)
        results.append(
            {
                "id": scenario.get("id"),
                "title": scenario.get("title"),
                "tags": list(scenario.get("tags") or []),
                "turns": turn_results,
            }
        )

    aggregate_metrics = {
        name: round(sum(values) / len(values), 4) if values else 0.0
        for name, values in sorted(metric_values.items())
    }
    aggregate_percentages = {
        f"{name}_percentage": round(value * 100, 2)
        for name, value in aggregate_metrics.items()
    }
    complete_turns = sum(1 for turn in all_turns if turn["complete"])
    passed = (
        bool(all_turns)
        and complete_turns == len(all_turns)
        and not observation_failures
        and not authority_violations
    )
    return {
        "contract": "semantic_projection_shadow_benchmark_result.v1",
        "source_contract": suite.get("contract"),
        "passed": passed,
        "scenario_count": len(results),
        "turn_count": len(all_turns),
        "complete_projection_turn_count": complete_turns,
        "projection_status_counts": dict(sorted(status_counts.items())),
        "metrics": aggregate_metrics,
        "metric_percentages": aggregate_percentages,
        "architecture": {
            "official_authority": "legacy",
            "semantic_projection_mode": "shadow",
            "authority_violation_count": len(authority_violations),
            "decision_influence_count": sum(
                1 for turn in all_turns if turn.get("decision_influence") is not False
            ),
            "state_mutation_count": sum(
                1 for turn in all_turns if turn.get("state_mutation") is not False
            ),
            "required_projection_count": len(PROJECTION_NAMES),
        },
        "observation_failure_count": len(observation_failures),
        "observation_failures": observation_failures,
        "authority_violations": authority_violations,
        "scenarios": results,
    }


def _complete_shadow_artifact(shadow: Mapping[str, Any]) -> bool:
    projection = shadow.get("semantic_projection") or {}
    comparison = shadow.get("comparison") or {}
    return bool(
        shadow.get("available")
        and shadow.get("semantic_projection_id")
        and shadow.get("semantic_projection_hash")
        and comparison.get("projection_hash")
        and all(name in projection for name in PROJECTION_NAMES)
        and set(shadow.get("projection_diff") or {}) == set(PROJECTION_NAMES)
        and shadow.get("legacy_projection")
    )


def _evaluate_observations(
    expected: Mapping[str, Any],
    projection: Mapping[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if "act" in expected:
        actual = (projection.get("conversational_act") or {}).get("act")
        checks.append(_check("act", expected["act"], actual))
    if "multiple_topics" in expected:
        actual = (projection.get("topic_projection") or {}).get("multiple_topics")
        checks.append(_check("multiple_topics", expected["multiple_topics"], actual))
    if "correction" in expected:
        corrections = (projection.get("fact_projection") or {}).get("corrections") or []
        actual = [item.get("operation") for item in corrections]
        checks.append(
            {
                "name": "correction",
                "expected": expected["correction"],
                "actual": actual,
                "passed": expected["correction"] in actual,
            }
        )
    if "topics" in expected:
        actual = {
            item.get("type")
            for item in (projection.get("topic_projection") or {}).get("topics") or []
        }
        expected_topics = set(expected.get("topics") or [])
        checks.append(
            {
                "name": "topics",
                "expected": sorted(expected_topics),
                "actual": sorted(actual),
                "passed": expected_topics <= actual,
            }
        )
    if "entities" in expected:
        actual = {
            item.get("value")
            for item in (projection.get("entity_projection") or {}).get("items") or []
        }
        expected_entities = set(expected.get("entities") or [])
        checks.append(
            {
                "name": "entities",
                "expected": sorted(expected_entities),
                "actual": sorted(actual),
                "passed": expected_entities <= actual,
            }
        )
    if "facts" in expected:
        actual = {
            item.get("type"): item.get("value")
            for item in (projection.get("fact_projection") or {}).get("items") or []
        }
        for name, value in (expected.get("facts") or {}).items():
            checks.append(_check(f"fact.{name}", value, actual.get(name)))
    return checks


def _check(name: str, expected: Any, actual: Any) -> dict[str, Any]:
    return {
        "name": name,
        "expected": expected,
        "actual": actual,
        "passed": expected == actual,
    }


def render_semantic_projection_benchmark_report(result: Mapping[str, Any]) -> str:
    metrics = result.get("metric_percentages") or {}
    lines = [
        "# ACA Semantic Projection Shadow Benchmark",
        "",
        f"- Passed: `{str(bool(result.get('passed'))).lower()}`",
        f"- Scenarios: `{result.get('scenario_count', 0)}`",
        f"- Turns: `{result.get('turn_count', 0)}`",
        f"- Complete projection turns: `{result.get('complete_projection_turn_count', 0)}`",
        f"- Observation failures: `{result.get('observation_failure_count', 0)}`",
        "",
        "## Projection Metrics",
        "",
    ]
    for name, value in metrics.items():
        lines.append(f"- {name.replace('_', ' ').title()}: `{value}%`")
    lines.extend(
        [
            "",
            "## Architecture",
            "",
            f"- Official authority: `{(result.get('architecture') or {}).get('official_authority')}`",
            f"- Semantic mode: `{(result.get('architecture') or {}).get('semantic_projection_mode')}`",
            f"- Authority violations: `{(result.get('architecture') or {}).get('authority_violation_count')}`",
            f"- Decision influence: `{(result.get('architecture') or {}).get('decision_influence_count')}`",
            f"- State mutation: `{(result.get('architecture') or {}).get('state_mutation_count')}`",
            "",
            "## Status Distribution",
            "",
        ]
    )
    for status, count in (result.get("projection_status_counts") or {}).items():
        lines.append(f"- {status}: `{count}`")
    return "\n".join(lines) + "\n"
