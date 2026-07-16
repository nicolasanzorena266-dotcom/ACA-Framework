from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

from aca_os.conversation_objective import ConversationObjective, ObjectiveDeterministicRealizer
from aca_os.llm_verbalization import DeterministicVerbalizationValidator, VerbalizationBrief


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONVERSATIONAL_FIRST_BENCHMARK_PATH = (
    ROOT / "benchmarks" / "conversations" / "aca_conversational_first_benchmark_v1.json"
)


def load_conversational_first_benchmark(path: str | Path | None = None) -> dict[str, Any]:
    benchmark_path = Path(path or DEFAULT_CONVERSATIONAL_FIRST_BENCHMARK_PATH)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    scenarios = list(data.get("scenarios") or [])
    return {
        "contract": "conversational_first_benchmark_suite.v1",
        "benchmark": data.get("benchmark", "aca_conversational_first.v1"),
        "path": str(benchmark_path),
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }


def run_conversational_first_benchmark(
    path: str | Path | None = None,
    *,
    scenario_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    suite = load_conversational_first_benchmark(path)
    scenarios = list(suite["scenarios"])
    if scenario_ids:
        selected = set(scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario.get("id") in selected]
    results = [_run_scenario(scenario) for scenario in scenarios]
    return {
        "contract": "conversational_first_benchmark_result.v1",
        "benchmark": suite["benchmark"],
        "scenario_count": len(results),
        "passed": bool(results) and all(result["passed"] for result in results),
        "metrics": {
            "objective_validity_percentage": _percentage(results, "objective_valid"),
            "llm_candidate_acceptance_percentage": _percentage(results, "candidate_accepted"),
            "domain_contamination_absence_percentage": _percentage(results, "domain_contamination_absent"),
            "legacy_replacement_percentage": _percentage(results, "legacy_replaced"),
            "question_budget_accuracy_percentage": _percentage(results, "question_budget_accurate"),
            "average_response_length": round(mean([len(result["visible_response"]) for result in results]), 2)
            if results
            else 0.0,
        },
        "results": results,
    }


def render_conversational_first_benchmark_report(result: Mapping[str, Any]) -> str:
    metrics = dict(result.get("metrics") or {})
    return "\n".join(
        [
            "# ACA Conversational First Benchmark",
            "",
            f"- Scenarios: {result.get('scenario_count', 0)}",
            f"- Passed: {result.get('passed')}",
            f"- Objective validity: {metrics.get('objective_validity_percentage', 0)}%",
            f"- Candidate acceptance: {metrics.get('llm_candidate_acceptance_percentage', 0)}%",
            f"- Domain contamination absent: {metrics.get('domain_contamination_absence_percentage', 0)}%",
            f"- Legacy response replaced: {metrics.get('legacy_replacement_percentage', 0)}%",
            f"- Question budget accuracy: {metrics.get('question_budget_accuracy_percentage', 0)}%",
        ]
    )


def _run_scenario(scenario: Mapping[str, Any]) -> dict[str, Any]:
    objective_data = dict(scenario.get("objective") or {})
    objective = ConversationObjective(
        goal=dict(objective_data.get("goal") or {}),
        missing_information=tuple(objective_data.get("missing_information") or []),
        next_step=dict(objective_data.get("next_step") or {}),
        empathy=str(objective_data.get("empathy") or "light"),
        tone=str(objective_data.get("tone") or "friendly_professional"),
        urgency=str(objective_data.get("urgency") or "normal"),
        constraints=tuple(objective_data.get("constraints") or []),
        conversation_mode=str(objective_data.get("conversation_mode") or "natural"),
        emoji=str(objective_data.get("emoji") or "allowed"),
    )
    fallback = ObjectiveDeterministicRealizer().realize(objective)
    candidate = str(scenario.get("candidate_response") or "").strip()
    semantic_context = dict(scenario.get("semantic_context") or {})
    brief = VerbalizationBrief(
        deterministic_response=fallback,
        user_message=str(scenario.get("user_message") or ""),
        authority_mode="conversation_objective",
        conversation_objective=objective.to_dict(),
        semantic_context=semantic_context,
        pending_information=tuple(
            {"slot": item} for item in objective.missing_information
        ),
    )
    validation = DeterministicVerbalizationValidator().validate(
        candidate=candidate,
        brief=brief,
        mode="strict",
    )
    visible = candidate if validation.accepted else fallback
    forbidden = [str(term).lower() for term in scenario.get("forbidden_terms") or []]
    contamination_absent = not any(term in visible.lower() for term in forbidden)
    expected_questions = int(
        objective.next_step.get("question_budget")
        if objective.next_step.get("question_budget") is not None
        else (1 if objective.next_step.get("action") == "request_information" else 0)
    )
    question_budget_accurate = visible.count("?") == expected_questions
    legacy = str(scenario.get("legacy_response") or "")
    result = {
        "id": scenario.get("id"),
        "objective_valid": objective.valid,
        "candidate_accepted": validation.accepted,
        "validation_rejections": list(validation.rejection_reasons),
        "domain_contamination_absent": contamination_absent,
        "legacy_replaced": bool(legacy) and visible != legacy,
        "question_budget_accurate": question_budget_accurate,
        "legacy_response": legacy,
        "deterministic_fallback": fallback,
        "candidate_response": candidate,
        "visible_response": visible,
    }
    result["passed"] = all(
        result[key]
        for key in (
            "objective_valid",
            "candidate_accepted",
            "domain_contamination_absent",
            "legacy_replaced",
            "question_budget_accurate",
        )
    )
    return result


def _percentage(items: Sequence[Mapping[str, Any]], key: str) -> float:
    return round(100.0 * sum(bool(item.get(key)) for item in items) / len(items), 2) if items else 0.0
