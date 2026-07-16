from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from statistics import mean
from typing import Any, Mapping, Sequence

from aca_core.text import normalize_text
from aca_os.llm_verbalization import (
    LLMProviderRequest,
    LLMProviderResponse,
    LLMVerbalizationConfig,
    LLMVerbalizer,
    VerbalizationBrief,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VERBALIZATION_BENCHMARK_PATH = (
    ROOT / "benchmarks" / "verbalization" / "aca_llm_verbalization_benchmark_v1.json"
)
DEFAULT_LANGUAGE_REALIZATION_BENCHMARK_PATH = (
    ROOT / "benchmarks" / "verbalization" / "aca_language_realization_benchmark_v1.json"
)


@dataclass
class _FixtureProvider:
    response: str
    provider_name: str = "benchmark_fixture"
    calls: int = 0

    def generate(self, request: LLMProviderRequest) -> LLMProviderResponse:
        self.calls += 1
        return LLMProviderResponse(
            text=self.response,
            provider=self.provider_name,
            model=request.model,
            request_id=f"fixture-{self.calls}",
        )


def load_llm_verbalization_benchmark(path: str | Path | None = None) -> dict[str, Any]:
    benchmark_path = Path(path or DEFAULT_VERBALIZATION_BENCHMARK_PATH)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    scenarios = list(data.get("scenarios") or [])
    return {
        "contract": "llm_verbalization_benchmark_suite.v1",
        "benchmark": data.get("benchmark", "aca_llm_verbalization_benchmark.v1"),
        "path": str(benchmark_path),
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }


def load_language_realization_benchmark(path: str | Path | None = None) -> dict[str, Any]:
    benchmark_path = Path(path or DEFAULT_LANGUAGE_REALIZATION_BENCHMARK_PATH)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    scenarios = list(data.get("scenarios") or [])
    return {
        "contract": "language_realization_benchmark_suite.v1",
        "benchmark": data.get("benchmark", "aca_language_realization_benchmark.v1"),
        "path": str(benchmark_path),
        "scenario_count": len(scenarios),
        "scenarios": scenarios,
    }


def run_language_realization_benchmark(
    path: str | Path | None = None,
    *,
    scenario_ids: Sequence[str] | None = None,
    live: bool = False,
    verbalizer: LLMVerbalizer | None = None,
) -> dict[str, Any]:
    suite = load_language_realization_benchmark(path)
    scenarios = list(suite["scenarios"])
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [item for item in scenarios if item.get("id") in wanted]

    live_verbalizer = verbalizer
    if live and live_verbalizer is None:
        live_verbalizer = LLMVerbalizer(config=LLMVerbalizationConfig.from_env())
    results = [
        _run_language_realization_scenario(
            scenario,
            verbalizer=live_verbalizer if live else None,
        )
        for scenario in scenarios
    ]
    total = len(results)
    latencies = [float(item["latency_ms"]) for item in results]
    quality = {
        "semantic_preservation_percentage": _result_percentage(
            results, "semantic_preserved"
        ),
        "repetition_reduction_percentage": _result_percentage(
            [item for item in results if item["repetition_reduction_applicable"]],
            "repetition_reduced",
        ),
        "bureaucratic_language_reduction_percentage": _result_percentage(
            results, "bureaucratic_language_reduced"
        ),
        "syntactic_variety_percentage": _result_percentage(results, "syntactic_variety"),
        "naturalness_percentage": _result_percentage(results, "naturalness_passed"),
        "validator_acceptance_percentage": _result_percentage(results, "accepted"),
        "runtime_authority_preservation_percentage": _result_percentage(
            results, "authority_preserved"
        ),
        "visible_response_improvement_percentage": _result_percentage(results, "passed"),
        "average_added_latency_ms": round(mean(latencies), 3) if latencies else 0.0,
        "maximum_added_latency_ms": round(max(latencies), 3) if latencies else 0.0,
    }
    return {
        "contract": "language_realization_benchmark_result.v1",
        "benchmark": suite["benchmark"],
        "mode": "live_provider" if live else "controlled_candidate",
        "scenario_count": total,
        "quality": quality,
        "passed": bool(results) and all(item["passed"] for item in results),
        "results": results,
    }


def render_language_realization_benchmark_report(result: Mapping[str, Any]) -> str:
    quality = dict(result.get("quality") or {})
    lines = [
        "# ACA Language Realization Benchmark",
        "",
        f"- Mode: {result.get('mode')}",
        f"- Scenarios: {result.get('scenario_count', 0)}",
        f"- Passed: {result.get('passed')}",
        f"- Semantic preservation: {quality.get('semantic_preservation_percentage', 0)}%",
        f"- Repetition reduction: {quality.get('repetition_reduction_percentage', 0)}%",
        f"- Bureaucratic-language reduction: {quality.get('bureaucratic_language_reduction_percentage', 0)}%",
        f"- Syntactic variety: {quality.get('syntactic_variety_percentage', 0)}%",
        f"- Naturalness: {quality.get('naturalness_percentage', 0)}%",
        f"- Validator acceptance: {quality.get('validator_acceptance_percentage', 0)}%",
        f"- Runtime authority preservation: {quality.get('runtime_authority_preservation_percentage', 0)}%",
        f"- Average added latency: {quality.get('average_added_latency_ms', 0)} ms",
        "",
        "## Scenarios",
        "",
    ]
    for scenario in result.get("results") or []:
        lines.append(
            f"- `{scenario.get('id')}`: accepted={scenario.get('accepted')}, "
            f"varied={scenario.get('syntactic_variety')}, passed={scenario.get('passed')}"
        )
    return "\n".join(lines) + "\n"


def run_llm_verbalization_benchmark(
    path: str | Path | None = None,
    *,
    scenario_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    suite = load_llm_verbalization_benchmark(path)
    scenarios = list(suite["scenarios"])
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [item for item in scenarios if item.get("id") in wanted]

    results = [_run_scenario(item) for item in scenarios]
    total = len(results) or 1
    accepted_expected = [item for item in results if item["expected_acceptance"]]
    rejected_expected = [item for item in results if not item["expected_acceptance"]]
    latencies = [float(item["latency_ms"]) for item in results]
    quality = {
        "naturalness_percentage": _percent(
            sum(1 for item in accepted_expected if item["naturalness_passed"]),
            len(accepted_expected),
        ),
        "runtime_fidelity_percentage": _percent(
            sum(1 for item in results if item["acceptance_matched"]),
            total,
        ),
        "fact_preservation_percentage": _tag_metric(results, "facts"),
        "operation_preservation_percentage": _tag_metric(results, "operations"),
        "case_state_preservation_percentage": _tag_metric(results, "case_state"),
        "governance_preservation_percentage": _tag_metric(results, "governance"),
        "hallucination_detection_percentage": _percent(
            sum(1 for item in rejected_expected if item["fallback_correct"]),
            len(rejected_expected),
        ),
        "rejected_change_count": sum(1 for item in results if not item["accepted"]),
        "fallback_correct_percentage": _percent(
            sum(1 for item in results if item["fallback_correct"]),
            total,
        ),
        "average_added_latency_ms": round(mean(latencies), 3) if latencies else 0.0,
        "maximum_added_latency_ms": round(max(latencies), 3) if latencies else 0.0,
    }
    return {
        "contract": "llm_verbalization_benchmark_result.v1",
        "benchmark": suite["benchmark"],
        "scenario_count": len(results),
        "quality": quality,
        "passed": all(item["passed"] for item in results),
        "results": results,
    }


def run_llm_verbalization_provider_comparison(
    path: str | Path | None = None,
    *,
    scenario_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Compare provider paths with the benchmark's fixed candidate responses.

    The benchmark intentionally keeps model output fixed. It measures adapter parity,
    validator parity and fallback behavior, not the relative quality of live models.
    """

    suite = load_llm_verbalization_benchmark(path)
    scenarios = list(suite["scenarios"])
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [item for item in scenarios if item.get("id") in wanted]

    profiles = {
        provider_name: _provider_profile(
            provider_name,
            [_run_scenario(item, provider_name=provider_name) for item in scenarios],
        )
        for provider_name in ("openai", "ollama")
    }
    profiles["deterministic"] = _provider_profile(
        "deterministic",
        [_run_deterministic_scenario(item) for item in scenarios],
    )
    return {
        "contract": "llm_verbalization_provider_comparison.v1",
        "benchmark": suite["benchmark"],
        "scenario_count": len(scenarios),
        "method": "fixed_candidate_provider_conformance",
        "live_network_calls": False,
        "profiles": profiles,
        "passed": all(profile["passed"] for profile in profiles.values()),
    }


def render_llm_verbalization_provider_comparison(result: Mapping[str, Any]) -> str:
    lines = [
        "# ACA LLM Provider Comparison",
        "",
        f"- Scenarios: {result.get('scenario_count', 0)}",
        f"- Method: {result.get('method')}",
        f"- Live network calls: {result.get('live_network_calls')}",
        f"- Passed: {result.get('passed')}",
        "",
        "| Profile | Fidelity | Naturalness | Hallucination safety | Fallbacks | Avg latency |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, profile in (result.get("profiles") or {}).items():
        quality = dict(profile.get("quality") or {})
        lines.append(
            f"| {name} | {quality.get('runtime_fidelity_percentage', 0)}% | "
            f"{quality.get('naturalness_percentage', 0)}% | "
            f"{quality.get('hallucination_safety_percentage', 0)}% | "
            f"{quality.get('fallback_count', 0)} | "
            f"{quality.get('average_added_latency_ms', 0)} ms |"
        )
    return "\n".join(lines) + "\n"


def render_llm_verbalization_benchmark_report(result: Mapping[str, Any]) -> str:
    quality = dict(result.get("quality") or {})
    lines = [
        "# ACA LLM Verbalization Benchmark",
        "",
        f"- Scenarios: {result.get('scenario_count', 0)}",
        f"- Passed: {result.get('passed')}",
        f"- Naturalness: {quality.get('naturalness_percentage', 0)}%",
        f"- Runtime fidelity: {quality.get('runtime_fidelity_percentage', 0)}%",
        f"- Hallucination detection: {quality.get('hallucination_detection_percentage', 0)}%",
        f"- Correct fallback: {quality.get('fallback_correct_percentage', 0)}%",
        f"- Average added latency: {quality.get('average_added_latency_ms', 0)} ms",
        "",
        "## Scenarios",
        "",
    ]
    for scenario in result.get("results") or []:
        lines.append(
            f"- `{scenario.get('id')}`: accepted={scenario.get('accepted')}, "
            f"fallback={scenario.get('fallback_correct')}, passed={scenario.get('passed')}"
        )
    return "\n".join(lines) + "\n"


def _run_scenario(
    scenario: Mapping[str, Any],
    *,
    provider_name: str = "benchmark_fixture",
) -> dict[str, Any]:
    provider = _FixtureProvider(
        str(scenario.get("verbalized_response") or ""),
        provider_name=provider_name,
    )
    config = LLMVerbalizationConfig(
        enabled=True,
        provider=provider_name,
        model="benchmark-model",
        api_key="benchmark-key",
        validation_mode=str(scenario.get("validation_mode") or "strict"),
    )
    verbalizer = LLMVerbalizer(config=config, provider=provider)
    brief_data = dict(scenario.get("brief") or {})
    brief = VerbalizationBrief(
        deterministic_response=str(scenario.get("deterministic_response") or ""),
        user_message=str(scenario.get("user_message") or ""),
        selected_operation=dict(brief_data.get("selected_operation") or {}),
        candidate_work=dict(brief_data.get("candidate_work") or {}),
        case_state=dict(brief_data.get("case_state") or {}),
        confirmed_facts=dict(brief_data.get("confirmed_facts") or {}),
        pending_information=tuple(brief_data.get("pending_information") or ()),
        response_directives=dict(brief_data.get("response_directives") or {}),
        policy=dict(brief_data.get("policy") or {}),
        governance=dict(brief_data.get("governance") or {}),
        executed_tools=tuple(brief_data.get("executed_tools") or ()),
    )
    original_authority = _authority_snapshot(brief)
    result = verbalizer.verbalize(brief)
    expected_acceptance = bool(scenario.get("expected_acceptance"))
    acceptance_matched = result.accepted == expected_acceptance
    fallback_correct = (
        result.final_response == result.verbalized_response
        if expected_acceptance
        else result.final_response == result.deterministic_response
    )
    authority_preserved = original_authority == _authority_snapshot(brief)
    naturalness_passed = _naturalness_passed(result.final_response, scenario)
    passed = acceptance_matched and fallback_correct and authority_preserved
    if expected_acceptance:
        passed = passed and naturalness_passed
    return {
        "id": scenario.get("id"),
        "tags": list(scenario.get("tags") or []),
        "expected_acceptance": expected_acceptance,
        "accepted": result.accepted,
        "acceptance_matched": acceptance_matched,
        "fallback_correct": fallback_correct,
        "authority_preserved": authority_preserved,
        "naturalness_passed": naturalness_passed,
        "fallback_reason": result.fallback_reason,
        "rejection_reasons": list(result.validation.rejection_reasons),
        "latency_ms": result.latency_ms,
        "final_response": result.final_response,
        "passed": passed,
    }


def _run_deterministic_scenario(scenario: Mapping[str, Any]) -> dict[str, Any]:
    brief = _brief_from_scenario(scenario)
    original_authority = _authority_snapshot(brief)
    result = LLMVerbalizer(
        config=LLMVerbalizationConfig(
            enabled=False,
            provider="ollama",
            model="benchmark-model",
        )
    ).verbalize(brief)
    authority_preserved = original_authority == _authority_snapshot(brief)
    fallback_correct = result.final_response == result.deterministic_response
    return {
        "id": scenario.get("id"),
        "tags": list(scenario.get("tags") or []),
        "expected_acceptance": False,
        "accepted": False,
        "acceptance_matched": True,
        "fallback_correct": fallback_correct,
        "authority_preserved": authority_preserved,
        "naturalness_passed": _naturalness_passed(result.final_response, scenario),
        "fallback_reason": result.fallback_reason,
        "rejection_reasons": list(result.validation.rejection_reasons),
        "latency_ms": result.latency_ms,
        "final_response": result.final_response,
        "passed": fallback_correct and authority_preserved and not result.provider_called,
    }


def _brief_from_scenario(scenario: Mapping[str, Any]) -> VerbalizationBrief:
    brief_data = dict(scenario.get("brief") or {})
    return VerbalizationBrief(
        deterministic_response=str(scenario.get("deterministic_response") or ""),
        user_message=str(scenario.get("user_message") or ""),
        selected_operation=dict(brief_data.get("selected_operation") or {}),
        candidate_work=dict(brief_data.get("candidate_work") or {}),
        case_state=dict(brief_data.get("case_state") or {}),
        confirmed_facts=dict(brief_data.get("confirmed_facts") or {}),
        pending_information=tuple(brief_data.get("pending_information") or ()),
        response_directives=dict(brief_data.get("response_directives") or {}),
        policy=dict(brief_data.get("policy") or {}),
        governance=dict(brief_data.get("governance") or {}),
        executed_tools=tuple(brief_data.get("executed_tools") or ()),
    )


def _provider_profile(name: str, results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(results)
    latencies = [float(item.get("latency_ms") or 0.0) for item in results]
    safe = [
        item
        for item in results
        if item.get("accepted") or item.get("fallback_correct")
    ]
    quality = {
        "runtime_fidelity_percentage": _percent(
            sum(1 for item in results if item.get("authority_preserved")), total
        ),
        "naturalness_percentage": _percent(
            sum(1 for item in results if item.get("naturalness_passed")), total
        ),
        "fact_preservation_percentage": _profile_tag_metric(results, "facts"),
        "operation_preservation_percentage": _profile_tag_metric(results, "operations"),
        "case_state_preservation_percentage": _profile_tag_metric(results, "case_state"),
        "governance_preservation_percentage": _profile_tag_metric(results, "governance"),
        "hallucination_safety_percentage": _percent(len(safe), total),
        "fallback_count": sum(1 for item in results if item.get("fallback_reason")),
        "average_added_latency_ms": round(mean(latencies), 3) if latencies else 0.0,
        "maximum_added_latency_ms": round(max(latencies), 3) if latencies else 0.0,
    }
    return {
        "provider": name,
        "scenario_count": total,
        "quality": quality,
        "passed": all(bool(item.get("passed")) for item in results),
        "results": list(results),
    }


def _profile_tag_metric(results: Sequence[Mapping[str, Any]], tag: str) -> float:
    scored = [item for item in results if tag in (item.get("tags") or [])]
    preserved = sum(
        1
        for item in scored
        if item.get("authority_preserved")
        and (item.get("accepted") or item.get("fallback_correct"))
    )
    return _percent(preserved, len(scored))


def _run_language_realization_scenario(
    scenario: Mapping[str, Any],
    *,
    verbalizer: LLMVerbalizer | None,
) -> dict[str, Any]:
    brief = _brief_from_scenario(scenario)
    original_authority = _authority_snapshot(brief)
    active_verbalizer = verbalizer
    if active_verbalizer is None:
        active_verbalizer = LLMVerbalizer(
            config=LLMVerbalizationConfig(
                enabled=True,
                provider="benchmark_fixture",
                model="language-realization-fixture",
                validation_mode="strict",
            ),
            provider=_FixtureProvider(
                str(scenario.get("verbalized_response") or ""),
                provider_name="benchmark_fixture",
            ),
        )

    result = active_verbalizer.verbalize(brief)
    candidate = str(result.verbalized_response or "")
    authority_preserved = original_authority == _authority_snapshot(brief)
    semantic_preserved = result.accepted and _semantic_requirements_preserved(
        candidate, scenario.get("semantic_requirements") or []
    )
    repetition_applicable = bool(scenario.get("expects_repetition_reduction"))
    repetition_reduced = (
        _repetition_count(candidate) < _repetition_count(brief.deterministic_response)
        if repetition_applicable and candidate
        else not repetition_applicable
    )
    bureaucratic_reduced = bool(candidate) and not _contains_any_phrase(
        candidate, scenario.get("bureaucratic_phrases") or []
    )
    syntactic_variety = bool(candidate) and _syntactically_varied(
        brief.deterministic_response,
        candidate,
        max_overlap=float(scenario.get("max_bigram_overlap") or 0.85),
    )
    naturalness_passed = (
        result.accepted
        and semantic_preserved
        and bureaucratic_reduced
        and syntactic_variety
    )
    passed = (
        naturalness_passed
        and repetition_reduced
        and authority_preserved
        and result.final_response == candidate
    )
    return {
        "id": scenario.get("id"),
        "deterministic_response": brief.deterministic_response,
        "verbalized_response": result.verbalized_response,
        "visible_response": result.final_response,
        "accepted": result.accepted,
        "fallback_reason": result.fallback_reason,
        "rejection_reasons": list(result.validation.rejection_reasons),
        "semantic_preserved": semantic_preserved,
        "repetition_reduction_applicable": repetition_applicable,
        "repetition_reduced": repetition_reduced,
        "bureaucratic_language_reduced": bureaucratic_reduced,
        "syntactic_variety": syntactic_variety,
        "bigram_overlap": _bigram_overlap(brief.deterministic_response, candidate),
        "naturalness_passed": naturalness_passed,
        "authority_preserved": authority_preserved,
        "latency_ms": result.latency_ms,
        "provider": result.provider,
        "model": result.model,
        "passed": passed,
    }


def _semantic_requirements_preserved(
    response: str,
    requirements: Sequence[Any],
) -> bool:
    normalized = normalize_text(response)
    for requirement in requirements:
        alternatives = requirement if isinstance(requirement, Sequence) and not isinstance(requirement, str) else [requirement]
        if not any(normalize_text(str(item)) in normalized for item in alternatives if item):
            return False
    return True


def _contains_any_phrase(response: str, phrases: Sequence[Any]) -> bool:
    normalized = normalize_text(response)
    return any(normalize_text(str(phrase)) in normalized for phrase in phrases if phrase)


def _repetition_count(response: str) -> int:
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", normalize_text(response))
        if len(token) >= 5
    ]
    return sum(max(tokens.count(token) - 1, 0) for token in set(tokens))


def _syntactically_varied(source: str, candidate: str, *, max_overlap: float) -> bool:
    if normalize_text(source) == normalize_text(candidate):
        return False
    return _bigram_overlap(source, candidate) <= max_overlap


def _bigram_overlap(source: str, candidate: str) -> float:
    source_tokens = re.findall(r"[a-z0-9]+", normalize_text(source))
    candidate_tokens = re.findall(r"[a-z0-9]+", normalize_text(candidate))
    source_bigrams = set(zip(source_tokens, source_tokens[1:]))
    candidate_bigrams = set(zip(candidate_tokens, candidate_tokens[1:]))
    union = source_bigrams | candidate_bigrams
    if not union:
        return 1.0 if source_tokens == candidate_tokens else 0.0
    return round(len(source_bigrams & candidate_bigrams) / len(union), 3)


def _result_percentage(results: Sequence[Mapping[str, Any]], key: str) -> float:
    return _percent(sum(1 for item in results if item.get(key)), len(results))


def _authority_snapshot(brief: VerbalizationBrief) -> dict[str, Any]:
    return {
        "selected_operation": deepcopy_mapping(brief.selected_operation),
        "candidate_work": deepcopy_mapping(brief.candidate_work),
        "case_state": deepcopy_mapping(brief.case_state),
        "policy": deepcopy_mapping(brief.policy),
        "governance": deepcopy_mapping(brief.governance),
        "executed_tools": [deepcopy_mapping(item) for item in brief.executed_tools],
    }


def deepcopy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(value), ensure_ascii=False, default=str))


def _naturalness_passed(response: str, scenario: Mapping[str, Any]) -> bool:
    normalized = normalize_text(response)
    forbidden = [normalize_text(item) for item in scenario.get("forbidden_phrases") or []]
    required = [normalize_text(item) for item in scenario.get("required_markers") or []]
    return not any(item and item in normalized for item in forbidden) and all(
        item in normalized for item in required
    )


def _tag_metric(results: Sequence[Mapping[str, Any]], tag: str) -> float:
    scored = [item for item in results if tag in (item.get("tags") or [])]
    return _percent(sum(1 for item in scored if item.get("passed")), len(scored))


def _percent(numerator: int, denominator: int) -> float:
    if not denominator:
        return 100.0
    return round((numerator / denominator) * 100.0, 2)
