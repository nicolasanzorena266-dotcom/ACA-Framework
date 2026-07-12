from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence

from aca_core.text import normalize_text
from aca_kernel.core.events import Event


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONVERSATION_BENCHMARK_PATH = (
    ROOT / "benchmarks" / "conversations" / "aca_cognitive_benchmark_v1.json"
)


REQUIRED_BENCHMARK_TAGS = {
    "denuncias",
    "consultas_cobertura",
    "franquicia",
    "CLEAS",
    "documentacion",
    "tiempos",
    "usuarios_ansiosos",
    "usuarios_que_cambian_de_tema",
    "usuarios_que_corrigen_informacion",
    "usuarios_que_responden_varias_preguntas_juntas",
    "usuarios_que_responden_parcialmente",
    "conversaciones_largas",
    "conversaciones_con_interrupciones",
    "recapitulaciones",
    "simplificacion",
    "profundizacion",
    "handoff",
}


COGNITIVE_CONTRACT_KEYS = {
    "conversation_act_recognition",
    "conversation_goal",
    "conversation_intent_model",
    "conversation_information_gain_plan",
    "conversation_plan",
    "conversation_response_plan",
    "conversation_fulfillment",
    "conversation_topic_stack",
    "conversation_slot_resolution",
    "conversation_fact_assimilation",
    "conversation_fact_revision",
    "conversation_mission_advancement",
    "conversation_state_runtime",
    "runtime_execution_engine",
    "runtime_execution_authority",
    "execution_step_outcomes",
    "zero_cost_action_plan",
    "zero_cost_execution_flow",
    "zero_cost_execution_plan",
    "zero_cost_decision_graph",
}


QUESTION_RE = re.compile(r"([^?]+\?)")


@dataclass(frozen=True)
class ConversationTurnSpec:
    user: str

    def to_dict(self) -> Dict[str, Any]:
        return {"user": self.user}


@dataclass(frozen=True)
class ConversationScenario:
    id: str
    title: str
    tags: tuple[str, ...]
    turns: tuple[ConversationTurnSpec, ...]
    expectations: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "tags": list(self.tags),
            "turns": [turn.to_dict() for turn in self.turns],
            "expectations": dict(self.expectations),
        }


def load_conversation_benchmark(
    path: str | Path | None = None,
) -> Dict[str, Any]:
    benchmark_path = Path(path or DEFAULT_CONVERSATION_BENCHMARK_PATH)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    scenarios = tuple(_scenario_from_dict(item) for item in data.get("scenarios", []))
    tags = sorted({tag for scenario in scenarios for tag in scenario.tags})
    missing_tags = sorted(REQUIRED_BENCHMARK_TAGS - set(tags))
    return {
        "contract": "conversation_benchmark_suite.v1",
        "benchmark": data.get("benchmark", "aca_cognitive_conversation_benchmark.v1"),
        "description": data.get("description", ""),
        "domain": data.get("domain", ""),
        "path": str(benchmark_path),
        "scenario_count": len(scenarios),
        "turn_count": sum(len(scenario.turns) for scenario in scenarios),
        "tags": tags,
        "missing_required_tags": missing_tags,
        "scenarios": scenarios,
    }


def run_cognitive_conversation_benchmark(
    path: str | Path | None = None,
    *,
    scenario_ids: Sequence[str] | None = None,
    max_scenarios: int | None = None,
    runtime_factory: Callable[[], Any] | None = None,
) -> Dict[str, Any]:
    """Run the permanent cognitive benchmark against the real ACA runtime."""

    if runtime_factory is None:
        from sdk.factory import build_galicia_runtime

        runtime_factory = build_galicia_runtime

    suite = load_conversation_benchmark(path)
    scenarios = list(suite["scenarios"])
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario.id in wanted]
    if max_scenarios is not None:
        scenarios = scenarios[:max_scenarios]

    results = [
        _run_conversation_scenario(
            scenario,
            runtime_factory=runtime_factory,
            ordinal=index + 1,
        )
        for index, scenario in enumerate(scenarios)
    ]
    aggregate = _aggregate_results(results, suite=suite)
    return {
        "contract": "cognitive_evaluation_benchmark_result.v1",
        "benchmark": suite["benchmark"],
        "description": suite["description"],
        "domain": suite["domain"],
        "source_path": suite["path"],
        "scenario_count": len(results),
        "turn_count": sum(result["metrics"]["turn_count"] for result in results),
        "coverage": aggregate["coverage"],
        "quality": aggregate["quality"],
        "errors": aggregate["errors"],
        "architecture": aggregate["architecture"],
        "scenarios": results,
    }


def render_cognitive_benchmark_report(result: Mapping[str, Any]) -> str:
    coverage = dict(result.get("coverage") or {})
    quality = dict(result.get("quality") or {})
    errors = dict(result.get("errors") or {})
    architecture = dict(result.get("architecture") or {})
    lines = [
        "# ACA Cognitive Conversation Benchmark",
        "",
        f"- Benchmark: `{result.get('benchmark')}`",
        f"- Scenarios: {result.get('scenario_count', 0)}",
        f"- Turns: {result.get('turn_count', 0)}",
        f"- Fulfillment rate: {quality.get('fulfilled_goal_rate', 0)}%",
        f"- Average questions per conversation: {quality.get('average_questions_per_conversation', 0)}",
        f"- Average questions per turn: {quality.get('average_questions_per_turn', 0)}",
        "",
        "## Coverage",
        "",
        f"- Required tags covered: {coverage.get('required_tag_coverage_percentage', 0)}%",
        f"- Missing required tags: {', '.join(coverage.get('missing_required_tags') or []) or 'none'}",
        f"- Contracts used: {', '.join(coverage.get('contracts_used') or []) or 'none'}",
        f"- Contracts never used: {', '.join(coverage.get('contracts_never_used') or []) or 'none'}",
        "",
        "## Quality",
        "",
        f"- Questions asked: {quality.get('questions_asked', 0)}",
        f"- Questions avoided: {quality.get('questions_avoided', 0)}",
        f"- Repeated questions: {quality.get('repeated_question_count', quality.get('repeated_questions', 0))}",
        f"- Opacity leaks: {quality.get('opacity_leaks', 0)}",
        f"- Unnecessary questions: {quality.get('unnecessary_questions', 0)}",
        f"- Reformulated questions: {quality.get('reformulated_questions', 0)}",
        f"- Answered before asking: {quality.get('answered_before_asking', 0)}",
        f"- Resumed topic success: {quality.get('resumed_topic_success', 0)}",
        f"- Topic changes: {quality.get('topic_changes', 0)}",
        f"- Focus recoveries: {quality.get('focus_recoveries', 0)}",
        f"- Replanning events: {quality.get('replanning_events', 0)}",
        f"- Error recovery actions: {quality.get('error_recovery_actions', 0)}",
        "",
        "## Errors",
        "",
    ]
    error_counts = errors.get("counts") or {}
    if error_counts:
        for error_name, count in sorted(error_counts.items()):
            lines.append(f"- {error_name}: {count}")
    else:
        lines.append("- none detected by deterministic benchmark rules")
    lines.extend(
        [
            "",
            "## Architecture",
            "",
            f"- Contracts with observed response value: {', '.join(architecture.get('value_contributing_contracts') or []) or 'none'}",
            f"- Redundant contract candidates: {', '.join(architecture.get('redundant_contract_candidates') or []) or 'none'}",
            f"- Complexity without observed benefit: {', '.join(architecture.get('complexity_without_observed_benefit') or []) or 'none'}",
            "",
            "## Scenario Summary",
            "",
        ]
    )
    for scenario in result.get("scenarios") or []:
        metrics = dict(scenario.get("metrics") or {})
        lines.append(
            f"- `{scenario.get('id')}`: status={metrics.get('final_fulfillment_status')}, "
            f"questions={metrics.get('questions_asked')}, "
            f"avoided={metrics.get('questions_avoided')}, "
            f"errors={len(scenario.get('errors') or [])}"
        )
    lines.append("")
    return "\n".join(lines)


def _scenario_from_dict(data: Mapping[str, Any]) -> ConversationScenario:
    return ConversationScenario(
        id=str(data["id"]),
        title=str(data.get("title") or data["id"]),
        tags=tuple(str(tag) for tag in data.get("tags", [])),
        turns=tuple(ConversationTurnSpec(user=str(turn["user"])) for turn in data.get("turns", [])),
        expectations=dict(data.get("expectations") or {}),
    )


def _run_conversation_scenario(
    scenario: ConversationScenario,
    *,
    runtime_factory: Callable[[], Any],
    ordinal: int,
) -> Dict[str, Any]:
    runtime = runtime_factory()
    conversation_id = f"benchmark:{ordinal}:{scenario.id}"
    turn_results = []
    for index, turn in enumerate(scenario.turns, start=1):
        state = runtime.process(
            Event(
                type="user_message",
                payload=turn.user,
                metadata={"conversation_id": conversation_id},
            )
        )
        turn_results.append(
            _turn_result(
                turn=turn,
                state=state,
                turn_index=index,
                introspection=runtime.inspect_runtime().to_dict(),
            )
        )
    metrics = _scenario_metrics(turn_results, scenario=scenario)
    errors = _scenario_errors(turn_results, metrics=metrics, scenario=scenario)
    contracts_used = sorted({contract for turn in turn_results for contract in turn["contracts_used"]})
    decisions = [
        decision
        for turn in turn_results
        for decision in turn.get("decisions_that_changed_response", [])
    ]
    return {
        "contract": "cognitive_conversation_scenario_result.v1",
        "id": scenario.id,
        "title": scenario.title,
        "tags": list(scenario.tags),
        "expectations": dict(scenario.expectations),
        "conversation_id": conversation_id,
        "metrics": metrics,
        "contracts_used": contracts_used,
        "contracts_never_used": sorted(COGNITIVE_CONTRACT_KEYS - set(contracts_used)),
        "decisions_that_changed_response": decisions,
        "irrelevant_contracts": _irrelevant_contracts(turn_results),
        "removable_steps_without_response_change": _removable_steps(turn_results, metrics=metrics),
        "errors": errors,
        "turns": turn_results,
    }


def _turn_result(
    *,
    turn: ConversationTurnSpec,
    state: Any,
    turn_index: int,
    introspection: Mapping[str, Any],
) -> Dict[str, Any]:
    facts = dict(getattr(state, "facts", {}) or {})
    response = str(getattr(state, "response", "") or "")
    runtime_record = _mapping(facts.get("conversation_state_runtime"))
    contracts_used = _contracts_used(facts)
    response_questions = _questions_from_response(response)
    info_plan = _payload_from_trace(facts.get("conversation_information_gain_plan"), "plan")
    response_plan = _payload_from_trace(facts.get("conversation_response_plan"), "plan")
    conversation_plan = _payload_from_trace(facts.get("conversation_plan"), "plan")
    fulfillment = _payload_from_trace(facts.get("conversation_fulfillment"), "fulfillment")
    intent_model = _payload_from_trace(facts.get("conversation_intent_model"), "model")
    topic_stack = _topic_stack(runtime_record, facts)
    tool_execution = _tool_execution_summary(facts)
    metrics = _turn_metrics(
        facts=facts,
        response=response,
        response_questions=response_questions,
        info_plan=info_plan,
        conversation_plan=conversation_plan,
        fulfillment=fulfillment,
        response_plan=response_plan,
        runtime_record=runtime_record,
        topic_stack=topic_stack,
    )
    decisions = _decisions_that_changed_response(
        response=response,
        info_plan=info_plan,
        response_plan=response_plan,
        conversation_plan=conversation_plan,
        fulfillment=fulfillment,
        intent_model=intent_model,
        facts=facts,
    )
    return {
        "contract": "cognitive_conversation_turn_result.v1",
        "turn": turn_index,
        "user": turn.user,
        "response": response,
        "response_word_count": len(response.split()),
        "questions": response_questions,
        "contracts_used": contracts_used,
        "metrics": metrics,
        "conversation_act": _selected_act(facts),
        "primary_user_need": _primary_user_need(response_plan),
        "dominant_concern": _dominant_concern(response_plan, intent_model),
        "selected_question": _selected_question(info_plan),
        "conversation_plan": _conversation_plan_summary(conversation_plan),
        "fulfillment": _fulfillment_summary(fulfillment),
        "topic_stack": topic_stack,
        "tool_execution": tool_execution,
        "runtime_execution_engine": _mapping(facts.get("runtime_execution_engine")),
        "decisions_that_changed_response": decisions,
        "errors": _turn_errors(
            response=response,
            response_questions=response_questions,
            info_plan=info_plan,
            response_plan=response_plan,
            fulfillment=fulfillment,
            decisions=decisions,
        ),
        "introspection": {
            "contracts": sorted(contracts_used),
            "conversation_state_runtime_available": bool(runtime_record.get("available")),
            "runtime_id": introspection.get("runtime_id"),
        },
    }


def _turn_metrics(
    *,
    facts: Mapping[str, Any],
    response: str,
    response_questions: Sequence[str],
    info_plan: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
    fulfillment: Mapping[str, Any],
    response_plan: Mapping[str, Any],
    runtime_record: Mapping[str, Any],
    topic_stack: Mapping[str, Any],
) -> Dict[str, Any]:
    question_metric = _mapping(info_plan.get("question_count_metric"))
    runtime_engine = _mapping(facts.get("runtime_execution_engine"))
    final_state = _mapping(runtime_record.get("final_state"))
    confirmed_facts = _mapping(final_state.get("confirmed_facts"))
    slots = _mapping(final_state.get("slots"))
    projections = list(runtime_record.get("projections") or [])
    fulfillment_goal = _mapping(fulfillment.get("fulfilled_goal"))
    recovery_actions = list(fulfillment.get("recovery_actions") or [])
    return {
        "questions_asked": len(response_questions),
        "questions_avoided": int(question_metric.get("avoided_question_count") or 0),
        "unnecessary_questions": 1 if response_questions and not info_plan.get("selected_question") else 0,
        "opacity_leaks": 1 if _has_cognitive_meta_comment(response) else 0,
        "reformulated_questions": _count_reformulated_questions(response_plan),
        "answered_before_asking": 1 if _answered_before_asking(response, response_questions) else 0,
        "resumed_topic_success": 1 if _resumed_topic_success(response, recovery_actions, projections) else 0,
        "topic_changes": _count_topic_changes(projections),
        "focus_recoveries": _count_focus_recoveries(projections, response=response),
        "mission_changes": _count_projection_reason(projections, "mission_advancement"),
        "replanning": _is_replanning_event(conversation_plan),
        "replanning_reason": conversation_plan.get("replanning_reason"),
        "fulfillment_status": fulfillment_goal.get("status"),
        "fulfilled_steps": len(fulfillment.get("fulfilled_steps") or []),
        "pending_steps": len(fulfillment.get("pending_steps") or []),
        "failed_steps": len(fulfillment.get("failed_steps") or []),
        "error_recovery_actions": len(recovery_actions),
        "memory_used": bool(getattr_value_or_default(facts, "memory_snapshot") or _mapping(final_state.get("derived_state")).get("memory_snapshot")),
        "facts_used": bool(confirmed_facts or facts.get("conversation_fact_assimilation")),
        "fact_count": len(confirmed_facts),
        "topic_stack_used": bool((topic_stack.get("topics") or topic_stack.get("active_topic"))),
        "slot_count": len(slots),
        "slots_used": bool(slots or facts.get("conversation_slot_resolution")),
        "conversation_plan_used": bool(conversation_plan),
        "response_plan_used": bool(facts.get("conversation_response_plan")),
        "runtime_engine": runtime_engine.get("official_engine"),
        "runtime_flow": runtime_engine.get("flow"),
        "runtime_equivalent": _mapping(runtime_engine.get("comparison")).get("equivalent"),
        "response_word_count": len(response.split()),
    }


def _scenario_metrics(
    turn_results: Sequence[Mapping[str, Any]],
    *,
    scenario: ConversationScenario,
) -> Dict[str, Any]:
    question_texts = [question for turn in turn_results for question in turn.get("questions", [])]
    normalized_questions = [_question_signature(question) for question in question_texts]
    repeated_questions = sum(count - 1 for count in Counter(normalized_questions).values() if count > 1)
    metrics = Counter()
    fulfillment_statuses = Counter()
    replanning_reasons = Counter()
    runtime_engines = Counter()
    runtime_flows = Counter()
    for turn in turn_results:
        turn_metrics = dict(turn.get("metrics") or {})
        for key in (
            "questions_asked",
            "questions_avoided",
            "unnecessary_questions",
            "opacity_leaks",
            "reformulated_questions",
            "answered_before_asking",
            "resumed_topic_success",
            "topic_changes",
            "focus_recoveries",
            "mission_changes",
            "fulfilled_steps",
            "pending_steps",
            "failed_steps",
            "error_recovery_actions",
            "fact_count",
            "slot_count",
        ):
            metrics[key] += int(turn_metrics.get(key) or 0)
        for key in (
            "memory_used",
            "facts_used",
            "topic_stack_used",
            "slots_used",
            "conversation_plan_used",
            "response_plan_used",
        ):
            if turn_metrics.get(key):
                metrics[key] += 1
        if turn_metrics.get("replanning"):
            metrics["replanning_events"] += 1
        if turn_metrics.get("fulfillment_status"):
            fulfillment_statuses[str(turn_metrics["fulfillment_status"])] += 1
        if turn_metrics.get("replanning_reason"):
            replanning_reasons[str(turn_metrics["replanning_reason"])] += 1
        if turn_metrics.get("runtime_engine"):
            runtime_engines[str(turn_metrics["runtime_engine"])] += 1
        if turn_metrics.get("runtime_flow"):
            runtime_flows[str(turn_metrics["runtime_flow"])] += 1

    final_fulfillment_status = _final_fulfillment_status(turn_results)
    objective_fulfilled = final_fulfillment_status in {"fulfilled", "completed"}
    expectation = scenario.expectations
    return {
        "turn_count": len(turn_results),
        "objective_fulfilled": objective_fulfilled,
        "final_fulfillment_status": final_fulfillment_status,
        "questions_asked": metrics["questions_asked"],
        "questions_avoided": metrics["questions_avoided"],
        "repeated_questions": repeated_questions,
        "repeated_question_count": repeated_questions,
        "unnecessary_questions": metrics["unnecessary_questions"],
        "opacity_leaks": metrics["opacity_leaks"],
        "reformulated_questions": metrics["reformulated_questions"],
        "answered_before_asking": metrics["answered_before_asking"],
        "resumed_topic_success": metrics["resumed_topic_success"],
        "topic_changes": metrics["topic_changes"],
        "focus_recoveries": metrics["focus_recoveries"],
        "mission_changes": metrics["mission_changes"],
        "replanning_events": metrics["replanning_events"],
        "fulfillment_statuses": dict(fulfillment_statuses),
        "fulfilled_steps": metrics["fulfilled_steps"],
        "pending_steps": metrics["pending_steps"],
        "failed_steps": metrics["failed_steps"],
        "error_recovery_actions": metrics["error_recovery_actions"],
        "memory_used_turns": metrics["memory_used"],
        "facts_used_turns": metrics["facts_used"],
        "fact_count": metrics["fact_count"],
        "topic_stack_used_turns": metrics["topic_stack_used"],
        "slots_used_turns": metrics["slots_used"],
        "slot_count": metrics["slot_count"],
        "conversation_plan_used_turns": metrics["conversation_plan_used"],
        "response_plan_used_turns": metrics["response_plan_used"],
        "runtime_engines": dict(runtime_engines),
        "runtime_flows": dict(runtime_flows),
        "replanning_reasons": dict(replanning_reasons),
        "max_questions_expectation": expectation.get("max_questions"),
        "meets_question_budget": (
            expectation.get("max_questions") is None
            or metrics["questions_asked"] <= int(expectation["max_questions"])
        ),
    }


def _scenario_errors(
    turn_results: Sequence[Mapping[str, Any]],
    *,
    metrics: Mapping[str, Any],
    scenario: ConversationScenario,
) -> list[Dict[str, Any]]:
    errors = []
    for turn in turn_results:
        for error in turn.get("errors") or []:
            errors.append(dict(error))
    if metrics.get("repeated_questions"):
        errors.append(
            {
                "type": "repeated_question",
                "severity": "medium",
                "evidence": {"count": metrics["repeated_questions"]},
            }
        )
    if (
        scenario.expectations.get("max_questions") is not None
        and metrics.get("questions_asked", 0) > int(scenario.expectations["max_questions"])
    ):
        errors.append(
            {
                "type": "too_many_questions",
                "severity": "medium",
                "evidence": {
                    "asked": metrics.get("questions_asked", 0),
                    "budget": scenario.expectations["max_questions"],
                },
            }
        )
    expected_contracts = set(scenario.expectations.get("should_use_contracts") or [])
    contracts_used = {contract for turn in turn_results for contract in turn.get("contracts_used", [])}
    missing_expected = sorted(expected_contracts - contracts_used)
    if missing_expected:
        errors.append(
            {
                "type": "expected_contract_not_used",
                "severity": "high",
                "evidence": {"contracts": missing_expected},
            }
        )
    if scenario.expectations.get("should_recover_focus") and not metrics.get("focus_recoveries"):
        errors.append(
            {
                "type": "lost_focus",
                "severity": "high",
                "evidence": {"scenario": scenario.id},
            }
        )
    if scenario.expectations.get("should_replan") and not metrics.get("replanning_events"):
        errors.append(
            {
                "type": "did_not_replan",
                "severity": "high",
                "evidence": {"scenario": scenario.id},
            }
        )
    expected_final = scenario.expectations.get("final_goal_status")
    if expected_final and metrics.get("final_fulfillment_status") != expected_final:
        errors.append(
            {
                "type": "goal_status_mismatch",
                "severity": "medium",
                "evidence": {
                    "expected": expected_final,
                    "actual": metrics.get("final_fulfillment_status"),
                },
            }
        )
    return errors


def _aggregate_results(results: Sequence[Mapping[str, Any]], *, suite: Mapping[str, Any]) -> Dict[str, Any]:
    tags = sorted({tag for result in results for tag in result.get("tags", [])})
    missing_required_tags = sorted(REQUIRED_BENCHMARK_TAGS - set(tags))
    contracts_used = sorted({contract for result in results for contract in result.get("contracts_used", [])})
    contract_counts = Counter(
        contract
        for result in results
        for turn in result.get("turns", [])
        for contract in turn.get("contracts_used", [])
    )
    decision_contract_counts = Counter(
        str(decision).split(":", 1)[0]
        for result in results
        for decision in result.get("decisions_that_changed_response", [])
    )
    errors = [error for result in results for error in result.get("errors", [])]
    error_counts = Counter(str(error.get("type")) for error in errors)
    metrics = Counter()
    fulfillment_final = Counter()
    runtime_engines = Counter()
    runtime_flows = Counter()
    for result in results:
        scenario_metrics = dict(result.get("metrics") or {})
        for key in (
            "turn_count",
            "questions_asked",
            "questions_avoided",
            "repeated_questions",
            "unnecessary_questions",
            "opacity_leaks",
            "reformulated_questions",
            "answered_before_asking",
            "resumed_topic_success",
            "topic_changes",
            "focus_recoveries",
            "mission_changes",
            "replanning_events",
            "fulfilled_steps",
            "pending_steps",
            "failed_steps",
            "error_recovery_actions",
            "memory_used_turns",
            "facts_used_turns",
            "topic_stack_used_turns",
            "slots_used_turns",
            "conversation_plan_used_turns",
            "response_plan_used_turns",
        ):
            metrics[key] += int(scenario_metrics.get(key) or 0)
        if scenario_metrics.get("objective_fulfilled"):
            metrics["fulfilled_scenarios"] += 1
        if scenario_metrics.get("final_fulfillment_status"):
            fulfillment_final[str(scenario_metrics["final_fulfillment_status"])] += 1
        runtime_engines.update(scenario_metrics.get("runtime_engines") or {})
        runtime_flows.update(scenario_metrics.get("runtime_flows") or {})

    scenario_count = len(results) or 1
    turn_count = metrics["turn_count"] or 1
    architecture = _architecture_audit(
        contracts_used=contracts_used,
        contract_counts=contract_counts,
        decision_contract_counts=decision_contract_counts,
        metrics=metrics,
    )
    return {
        "coverage": {
            "scenario_count": len(results),
            "turn_count": metrics["turn_count"],
            "required_tags": sorted(REQUIRED_BENCHMARK_TAGS),
            "tags_covered": tags,
            "missing_required_tags": missing_required_tags,
            "required_tag_coverage_percentage": _percent(
                len(REQUIRED_BENCHMARK_TAGS) - len(missing_required_tags),
                len(REQUIRED_BENCHMARK_TAGS),
            ),
            "contracts_used": contracts_used,
            "contract_use_counts": dict(sorted(contract_counts.items())),
            "contracts_never_used": sorted(COGNITIVE_CONTRACT_KEYS - set(contracts_used)),
        },
        "quality": {
            "fulfilled_goal_rate": _percent(metrics["fulfilled_scenarios"], scenario_count),
            "final_fulfillment_statuses": dict(fulfillment_final),
            "questions_asked": metrics["questions_asked"],
            "questions_avoided": metrics["questions_avoided"],
            "average_questions_per_conversation": round(metrics["questions_asked"] / scenario_count, 2),
            "average_questions_per_turn": round(metrics["questions_asked"] / turn_count, 2),
            "repeated_questions": metrics["repeated_questions"],
            "repeated_question_count": metrics["repeated_questions"],
            "unnecessary_questions": metrics["unnecessary_questions"],
            "opacity_leaks": metrics["opacity_leaks"],
            "reformulated_questions": metrics["reformulated_questions"],
            "answered_before_asking": metrics["answered_before_asking"],
            "resumed_topic_success": metrics["resumed_topic_success"],
            "topic_changes": metrics["topic_changes"],
            "focus_recoveries": metrics["focus_recoveries"],
            "mission_changes": metrics["mission_changes"],
            "replanning_events": metrics["replanning_events"],
            "fulfilled_steps": metrics["fulfilled_steps"],
            "pending_steps": metrics["pending_steps"],
            "failed_steps": metrics["failed_steps"],
            "error_recovery_actions": metrics["error_recovery_actions"],
            "memory_used_turns": metrics["memory_used_turns"],
            "facts_used_turns": metrics["facts_used_turns"],
            "topic_stack_used_turns": metrics["topic_stack_used_turns"],
            "slots_used_turns": metrics["slots_used_turns"],
            "conversation_plan_used_turns": metrics["conversation_plan_used_turns"],
            "response_plan_used_turns": metrics["response_plan_used_turns"],
            "runtime_engines": dict(runtime_engines),
            "runtime_flows": dict(runtime_flows),
        },
        "errors": {
            "count": len(errors),
            "counts": dict(sorted(error_counts.items())),
            "examples": errors[:20],
        },
        "architecture": architecture,
    }


def _architecture_audit(
    *,
    contracts_used: Sequence[str],
    contract_counts: Counter,
    decision_contract_counts: Counter,
    metrics: Counter,
) -> Dict[str, Any]:
    used = set(contracts_used)
    never_used = COGNITIVE_CONTRACT_KEYS - used
    value_contracts = sorted(
        contract
        for contract in used
        if decision_contract_counts.get(contract, 0) > 0
        or contract
        in {
            "conversation_fact_assimilation",
            "conversation_fact_revision",
            "conversation_slot_resolution",
            "runtime_execution_engine",
        }
    )
    used_without_decision = sorted(
        contract
        for contract in used
        if decision_contract_counts.get(contract, 0) == 0
        and contract
        not in {
            "conversation_fact_assimilation",
            "conversation_fact_revision",
            "conversation_slot_resolution",
            "runtime_execution_engine",
            "conversation_state_runtime",
        }
    )
    redundant_candidates = []
    if {"conversation_goal", "conversation_fulfillment"} <= used and decision_contract_counts.get("conversation_goal", 0) == 0:
        redundant_candidates.append("conversation_goal may be an intermediate projection if fulfillment and response plan own observable behavior")
    if {"conversation_plan", "conversation_fulfillment"} <= used and metrics.get("replanning_events", 0) == 0:
        redundant_candidates.append("conversation_plan has low observed value without replanning events")
    if {"zero_cost_execution_flow", "zero_cost_execution_plan"} <= used:
        redundant_candidates.append("zero_cost_execution_flow and zero_cost_execution_plan remain adjacent projections; future consolidation may be possible")

    complexity_without_benefit = []
    if metrics.get("memory_used_turns", 0) == 0:
        complexity_without_benefit.append("memory_engine did not influence the sampled conversations")
    if metrics.get("topic_stack_used_turns", 0) > 0 and metrics.get("focus_recoveries", 0) == 0:
        complexity_without_benefit.append("topic_stack was present but did not recover focus in this run")
    for contract in never_used:
        complexity_without_benefit.append(f"{contract} was never observed in the benchmark run")

    fusion_candidates = []
    if "conversation_response_plan" in used and "conversation_intent_model" in used:
        fusion_candidates.append(
            "conversation_intent_model and conversation_response_plan should stay separate only while implicit concern evidence is reused outside responses"
        )
    if "conversation_plan" in used and "conversation_fulfillment" in used:
        fusion_candidates.append(
            "conversation_plan and conversation_fulfillment form a plan/evaluate pair; do not add more turn-plan contracts before proving need"
        )

    return {
        "contracts_used": sorted(used),
        "contracts_never_used": sorted(never_used),
        "contract_use_counts": dict(sorted(contract_counts.items())),
        "response_decision_contract_counts": dict(sorted(decision_contract_counts.items())),
        "value_contributing_contracts": value_contracts,
        "contracts_used_without_observed_response_decision": used_without_decision,
        "redundant_contract_candidates": redundant_candidates,
        "fusion_candidates": fusion_candidates,
        "complexity_without_observed_benefit": complexity_without_benefit,
        "critical_takeaway": _architecture_takeaway(value_contracts, used_without_decision, complexity_without_benefit),
    }


def _architecture_takeaway(
    value_contracts: Sequence[str],
    used_without_decision: Sequence[str],
    complexity_without_benefit: Sequence[str],
) -> str:
    if complexity_without_benefit:
        return "The benchmark is now able to identify architecture that exists without observed conversational benefit."
    if len(value_contracts) > len(used_without_decision):
        return "Most observed contracts contributed to conversation behavior in this run."
    return "Several contracts are observable but not yet proven to change user-facing behavior."


def _contracts_used(facts: Mapping[str, Any]) -> list[str]:
    return sorted(key for key in COGNITIVE_CONTRACT_KEYS if facts.get(key) not in (None, {}, []))


def _payload_from_trace(value: Any, payload_key: str) -> Dict[str, Any]:
    trace = _mapping(value)
    payload = trace.get(payload_key)
    if isinstance(payload, Mapping):
        return dict(payload)
    return trace


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _questions_from_response(response: str) -> list[str]:
    return [match.group(1).strip() for match in QUESTION_RE.finditer(response or "")]


def _question_signature(question: str) -> str:
    return normalize_text(question).strip(" .?!")


def _selected_act(facts: Mapping[str, Any]) -> Dict[str, Any]:
    trace = _mapping(facts.get("conversation_act_recognition"))
    selected = _mapping(trace.get("selected"))
    return {
        "act": selected.get("act"),
        "confidence": selected.get("confidence"),
        "reason": selected.get("reason"),
    }


def _selected_question(info_plan: Mapping[str, Any]) -> Dict[str, Any]:
    selected = _mapping(info_plan.get("selected_question"))
    if not selected:
        return {}
    return {
        "slot": selected.get("slot"),
        "question": selected.get("question"),
        "purpose": selected.get("purpose"),
        "expected_information_gain": selected.get("expected_information_gain"),
        "affected_decisions": list(selected.get("affected_decisions") or []),
    }


def _primary_user_need(response_plan: Mapping[str, Any]) -> Dict[str, Any]:
    need = _mapping(response_plan.get("primary_user_need"))
    return {
        "key": need.get("key"),
        "label": need.get("label"),
        "confidence": need.get("confidence"),
        "source": need.get("source"),
    }


def _dominant_concern(response_plan: Mapping[str, Any], intent_model: Mapping[str, Any]) -> Dict[str, Any]:
    concern = _mapping(response_plan.get("dominant_concern")) or _mapping(intent_model.get("dominant_concern"))
    return {
        "key": concern.get("key"),
        "label": concern.get("label"),
        "confidence": concern.get("confidence"),
        "source": concern.get("source"),
    }


def _conversation_plan_summary(plan: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "replanning_reason": plan.get("replanning_reason"),
        "completed_steps": [_step_id(step) for step in plan.get("completed_steps") or []],
        "pending_steps": [_step_id(step) for step in plan.get("pending_steps") or []],
        "abandoned_steps": [_step_id(step) for step in plan.get("abandoned_steps") or []],
        "inserted_steps": [_step_id(step) for step in plan.get("inserted_steps") or []],
        "skipped_steps": [_step_id(step) for step in plan.get("skipped_steps") or []],
        "conversation_progress": dict(plan.get("conversation_progress") or {}),
    }


def _fulfillment_summary(fulfillment: Mapping[str, Any]) -> Dict[str, Any]:
    goal = _mapping(fulfillment.get("fulfilled_goal"))
    return {
        "status": goal.get("status"),
        "satisfied": goal.get("satisfied"),
        "completion_reason": fulfillment.get("completion_reason"),
        "fulfillment_confidence": fulfillment.get("fulfillment_confidence"),
        "fulfilled_steps": [_step_id(step) for step in fulfillment.get("fulfilled_steps") or []],
        "pending_steps": [_step_id(step) for step in fulfillment.get("pending_steps") or []],
        "failed_steps": [_step_id(step) for step in fulfillment.get("failed_steps") or []],
        "recovery_actions": [
            _mapping(action).get("action")
            for action in fulfillment.get("recovery_actions") or []
        ],
    }


def _topic_stack(runtime_record: Mapping[str, Any], facts: Mapping[str, Any]) -> Dict[str, Any]:
    topic_projection = _mapping(runtime_record.get("topic_stack")) or _mapping(facts.get("conversation_topic_stack"))
    active_topic = _mapping(runtime_record.get("active_topic")) or _mapping(facts.get("conversation_active_topic"))
    topics = list(topic_projection.get("topics") or [])
    return {
        "active_topic": active_topic,
        "topic_count": len(topics),
        "topics": [
            {
                "id": _mapping(topic).get("id"),
                "type": _mapping(topic).get("type"),
                "status": _mapping(topic).get("status"),
                "summary": _mapping(topic).get("summary"),
            }
            for topic in topics
        ],
    }


def _tool_execution_summary(facts: Mapping[str, Any]) -> Dict[str, Any]:
    engine = _mapping(facts.get("runtime_execution_engine"))
    executions = list(engine.get("tool_executions") or [])
    return {
        "count": len(executions),
        "executions": [
            {
                "tool": _mapping(execution).get("tool_name") or _mapping(execution).get("adapter"),
                "mode": _mapping(execution).get("mode"),
                "action": _mapping(execution).get("action"),
                "executed": _mapping(execution).get("executed"),
            }
            for execution in executions
        ],
    }


def _decisions_that_changed_response(
    *,
    response: str,
    info_plan: Mapping[str, Any],
    response_plan: Mapping[str, Any],
    conversation_plan: Mapping[str, Any],
    fulfillment: Mapping[str, Any],
    intent_model: Mapping[str, Any],
    facts: Mapping[str, Any],
) -> list[str]:
    normalized_response = normalize_text(response)
    decisions: list[str] = []
    primary = _mapping(response_plan.get("primary_user_need"))
    if primary.get("key") and _need_appears_in_response(primary, normalized_response):
        decisions.append(f"conversation_response_plan:primary_user_need:{primary['key']}")
    concern = _mapping(response_plan.get("dominant_concern")) or _mapping(intent_model.get("dominant_concern"))
    if concern.get("key") and _need_appears_in_response(concern, normalized_response):
        decisions.append(f"conversation_intent_model:dominant_concern:{concern['key']}")
    selected_question = _mapping(info_plan.get("selected_question"))
    if selected_question.get("question") and _question_signature(selected_question["question"]) in normalized_response:
        decisions.append(f"conversation_information_gain_plan:selected_question:{selected_question.get('slot')}")
    if conversation_plan.get("inserted_steps"):
        for step in conversation_plan.get("inserted_steps") or []:
            step_id = _step_id(step)
            if step_id:
                decisions.append(f"conversation_plan:inserted_step:{step_id}")
    if conversation_plan.get("skipped_steps"):
        for step in conversation_plan.get("skipped_steps") or []:
            step_id = _step_id(step)
            if step_id:
                decisions.append(f"conversation_plan:skipped_step:{step_id}")
    for action in fulfillment.get("recovery_actions") or []:
        action_name = _mapping(action).get("action")
        if action_name:
            decisions.append(f"conversation_fulfillment:recovery_action:{action_name}")
    if facts.get("conversation_slot_resolution"):
        decisions.append("conversation_slot_resolution:pending_answer")
    if facts.get("conversation_fact_assimilation"):
        decisions.append("conversation_fact_assimilation:new_fact")
    if facts.get("conversation_fact_revision"):
        decisions.append("conversation_fact_revision:fact_updated")
    return sorted(set(decisions))


def _need_appears_in_response(need: Mapping[str, Any], normalized_response: str) -> bool:
    key = normalize_text(str(need.get("key") or ""))
    label = normalize_text(str(need.get("label") or ""))
    if key and any(part and part in normalized_response for part in key.split("_")):
        return True
    label_terms = [term for term in label.split() if len(term) > 5]
    return bool(label_terms and any(term in normalized_response for term in label_terms[:4]))


def _turn_errors(
    *,
    response: str,
    response_questions: Sequence[str],
    info_plan: Mapping[str, Any],
    response_plan: Mapping[str, Any],
    fulfillment: Mapping[str, Any],
    decisions: Sequence[str],
) -> list[Dict[str, Any]]:
    errors = []
    selected_question = _mapping(info_plan.get("selected_question"))
    if response_questions and not selected_question:
        errors.append(
            {
                "type": "unnecessary_question",
                "severity": "medium",
                "evidence": {"questions": list(response_questions)},
            }
        )
    if len(response_questions) > 1:
        errors.append(
            {
                "type": "asked_too_much_in_one_turn",
                "severity": "low",
                "evidence": {"questions": list(response_questions)},
            }
        )
    planned_question = _planned_question_for_response(response_plan, selected_question)
    if planned_question and response_questions:
        expected = _question_signature(planned_question)
        asked = [_question_signature(question) for question in response_questions]
        if expected not in " ".join(asked):
            errors.append(
                {
                    "type": "asked_different_question_than_planned",
                    "severity": "high",
                    "evidence": {
                        "planned_question": planned_question,
                        "selected_question": selected_question,
                        "asked": list(response_questions),
                    },
                }
            )
    goal = _mapping(fulfillment.get("fulfilled_goal"))
    if goal.get("status") == "failed" and not fulfillment.get("recovery_actions"):
        errors.append(
            {
                "type": "poor_recovery",
                "severity": "high",
                "evidence": {"fulfillment": _fulfillment_summary(fulfillment)},
            }
        )
    if response and len(response.split()) > 95:
        errors.append(
            {
                "type": "excessive_explanation",
                "severity": "low",
                "evidence": {"word_count": len(response.split())},
            }
        )
    primary = _mapping(response_plan.get("primary_user_need"))
    if primary.get("key") and not any(decision.startswith("conversation_response_plan") for decision in decisions):
        if not selected_question and len(response.split()) < 10:
            errors.append(
                {
                    "type": "insufficient_explanation",
                    "severity": "medium",
                    "evidence": {"primary_user_need": primary},
                }
            )
    if _has_cognitive_meta_comment(response):
        errors.append(
            {
                "type": "cognitive_meta_comment_leaked",
                "severity": "high",
                "evidence": {"response": response},
            }
        )
    return errors


def _has_cognitive_meta_comment(response: str) -> bool:
    normalized = normalize_text(response)
    forbidden = (
        "no voy",
        "no te vuelvo",
        "para no girar",
        "cambiar de estrategia",
        "mision actual",
        "mision activa",
        "misma mision",
        "sin reiniciar",
        "dejo suspendido",
        "contrato conversacional",
        "plan conversacional",
        "conversation plan",
        "conversation goal",
        "estado conversacional",
        "runtime",
        "planificacion",
        "check_claim_report_loaded",
        "check_documentation_available",
        "ask_user_role",
        "ask_injuries",
    )
    return any(phrase in normalized for phrase in forbidden)


def _planned_question_for_response(
    response_plan: Mapping[str, Any],
    selected_question: Mapping[str, Any],
) -> str:
    for item in response_plan.get("required_information") or []:
        if isinstance(item, Mapping) and item.get("question"):
            return str(item["question"])
    return str(selected_question.get("question") or "")


def _count_reformulated_questions(response_plan: Mapping[str, Any]) -> int:
    return sum(
        1
        for item in response_plan.get("required_information") or []
        if isinstance(item, Mapping) and item.get("question_was_reformulated")
    )


def _answered_before_asking(response: str, response_questions: Sequence[str]) -> bool:
    if not response_questions:
        return False
    first_question_index = str(response).find("?")
    if first_question_index <= 0:
        return False
    prefix = str(response)[:first_question_index]
    normalized = normalize_text(prefix)
    if len(prefix.split()) < 10:
        return False
    return any(
        marker in normalized
        for marker in (
            "sobre",
            "normalmente",
            "depende",
            "conviene",
            "no significa",
            "para documentacion",
            "respecto",
        )
    )


def _resumed_topic_success(
    response: str,
    recovery_actions: Sequence[Any],
    projections: Sequence[Any],
) -> bool:
    normalized = normalize_text(response)
    has_resume_action = any(
        _mapping(action).get("action") == "resume_main_plan"
        for action in recovery_actions
    )
    has_resume_projection = any(
        _mapping(projection).get("reason") == "topic_stack_transition"
        and _mapping(projection).get("transition") == "topic_resumed"
        for projection in projections
    )
    has_transition_text = any(
        phrase in normalized
        for phrase in (
            "respecto a tu denuncia",
            "retomo",
            "volvamos",
            "para seguir",
        )
    )
    return (has_resume_action or has_resume_projection) and has_transition_text


def _irrelevant_contracts(turn_results: Sequence[Mapping[str, Any]]) -> list[str]:
    used = {contract for turn in turn_results for contract in turn.get("contracts_used", [])}
    decision_contracts = {
        str(decision).split(":", 1)[0]
        for turn in turn_results
        for decision in turn.get("decisions_that_changed_response", [])
    }
    infrastructural = {
        "conversation_state_runtime",
        "runtime_execution_engine",
        "runtime_execution_authority",
        "execution_step_outcomes",
        "zero_cost_action_plan",
        "zero_cost_execution_flow",
        "zero_cost_execution_plan",
        "zero_cost_decision_graph",
    }
    return sorted(used - decision_contracts - infrastructural)


def _removable_steps(
    turn_results: Sequence[Mapping[str, Any]],
    *,
    metrics: Mapping[str, Any],
) -> list[Dict[str, Any]]:
    candidates = []
    if metrics.get("memory_used_turns", 0) == 0:
        candidates.append(
            {
                "candidate": "memory_snapshot",
                "reason": "No benchmark turn observed memory affecting the response.",
                "risk": "medium",
            }
        )
    irrelevant = _irrelevant_contracts(turn_results)
    for contract in irrelevant:
        candidates.append(
            {
                "candidate": contract,
                "reason": "Observed as a projection but not tied to a response-changing decision in this scenario.",
                "risk": "unknown",
            }
        )
    return candidates


def _is_replanning_event(plan: Mapping[str, Any]) -> bool:
    reason = str(plan.get("replanning_reason") or "")
    return bool(
        reason
        and reason
        not in {
            "plan_initialized",
            "plan_still_valid",
            "no_active_plan",
        }
    )


def _count_projection_reason(projections: Sequence[Any], reason: str) -> int:
    return sum(1 for projection in projections if _mapping(projection).get("reason") == reason)


def _count_topic_changes(projections: Sequence[Any]) -> int:
    transitions = {
        "topic_switched",
        "topic_resumed",
        "topic_suspended",
        "topic_shift",
    }
    return sum(
        1
        for projection in projections
        if _mapping(projection).get("reason") == "topic_stack_transition"
        and _mapping(projection).get("transition") in transitions
    )


def _count_focus_recoveries(projections: Sequence[Any], *, response: str) -> int:
    count = sum(
        1
        for projection in projections
        if _mapping(projection).get("reason") == "topic_stack_transition"
        and _mapping(projection).get("transition") == "topic_resumed"
    )
    normalized_response = normalize_text(response)
    if "volvamos" in normalized_response or "retomo" in normalized_response or "seguimos" in normalized_response:
        count += 1
    return count


def _final_fulfillment_status(turn_results: Sequence[Mapping[str, Any]]) -> str | None:
    for turn in reversed(turn_results):
        status = _mapping(turn.get("fulfillment")).get("status")
        if status:
            return str(status)
    return None


def _step_id(step: Any) -> str:
    if isinstance(step, Mapping):
        return str(step.get("id") or "")
    return ""


def getattr_value_or_default(mapping: Mapping[str, Any], key: str, default: Any = None) -> Any:
    return mapping.get(key, default)


def _percent(value: int | float, total: int | float) -> float:
    if not total:
        return 0.0
    return round((float(value) / float(total)) * 100, 2)
