from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence
from uuid import uuid4

from aca_core.text import normalize_text
from aca_kernel.core.events import Event
from aca_os.operational_work_mapper import (
    compare_operational_work_to_expected,
    map_operational_work,
)
from aca_os.operational_governance_gate import (
    assess_operational_governance,
    compare_governance_to_expected,
)
from aca_os.operational_audit_ledger import (
    compare_ledger_to_expected,
    finalize_operational_audit_ledger,
    JsonlOperationalAuditLedgerStore,
    project_operational_audit_ledger,
)
from aca_os.operational_tools import HandoffPackageAdapter, HandoffPackageDryRunAdapter
from aca_os.tool_engine import ToolExecutionContext, ToolExecutionMode, ToolRequest, ToolResult


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONVERSATION_BENCHMARK_PATH = (
    ROOT / "benchmarks" / "conversations" / "aca_cognitive_benchmark_v1.json"
)
DEFAULT_OPERATIONAL_BENCHMARK_PATH = (
    ROOT / "benchmarks" / "operational" / "aca_operational_benchmark_v1.json"
)
DEFAULT_OPERATIONAL_REAL_WORLD_BENCHMARK_PATH = (
    ROOT / "benchmarks" / "operational" / "aca_operational_real_world_benchmark_v1.json"
)
DEFAULT_OPERATIONAL_GOVERNANCE_BENCHMARK_PATH = (
    ROOT / "benchmarks" / "operational" / "aca_operational_governance_benchmark_v1.json"
)
DEFAULT_OPERATIONAL_AUDIT_LEDGER_BENCHMARK_PATH = (
    ROOT / "benchmarks" / "operational" / "aca_operational_audit_ledger_benchmark_v1.json"
)
DEFAULT_OPERATIONAL_DRY_RUN_BENCHMARK_PATH = (
    ROOT / "benchmarks" / "operational" / "aca_operational_dry_run_benchmark_v1.json"
)
DEFAULT_OPERATIONAL_PRODUCTION_BENCHMARK_PATH = (
    ROOT / "benchmarks" / "operational" / "aca_operational_production_benchmark_v1.json"
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


def run_public_runtime_adapter_benchmark(
    path: str | Path | None = None,
    *,
    scenario_ids: Sequence[str] | None = None,
    max_scenarios: int | None = None,
    runtime_factory: Callable[[], Any] | None = None,
) -> Dict[str, Any]:
    """Validate that the public endpoint adapter uses the canonical Runtime pipeline."""

    if runtime_factory is None:
        from sdk.factory import build_galicia_runtime

        runtime_factory = build_galicia_runtime

    from aca_os.public_conversation_product_layer import PublicConversationProductLayer

    suite = load_conversation_benchmark(path)
    scenarios = list(suite["scenarios"])
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario.id in wanted]
    if max_scenarios is not None:
        scenarios = scenarios[:max_scenarios]

    scenario_results = []
    for ordinal, scenario in enumerate(scenarios, start=1):
        runtime = runtime_factory()
        public_layer = PublicConversationProductLayer.from_path("plugins")
        runtime_conversation_id = f"adapter-benchmark:runtime:{ordinal}:{scenario.id}"
        public_conversation_id = f"adapter-benchmark:public:{ordinal}:{scenario.id}"
        turns = []
        for turn_index, turn in enumerate(scenario.turns, start=1):
            runtime_state = runtime.process(
                Event(
                    type="user_message",
                    payload=turn.user,
                    metadata={"conversation_id": runtime_conversation_id},
                )
            )
            public_result = public_layer.run(
                message=turn.user,
                conversation_id=public_conversation_id,
            )
            runtime_facts = dict(runtime_state.facts or {})
            public_diagnostic = dict(public_result.get("diagnostic_view") or {})
            runtime_engine = dict(runtime_facts.get("runtime_execution_engine") or {})
            public_engine = dict(public_diagnostic.get("runtime_execution_engine") or {})
            runtime_plan = dict(runtime_facts.get("conversation_plan") or {})
            public_plan = dict(public_diagnostic.get("conversation_plan") or {})
            turns.append(
                {
                    "turn": turn_index,
                    "user": turn.user,
                    "runtime_response": runtime_state.response,
                    "public_response": public_result.get("response"),
                    "same_response": runtime_state.response == public_result.get("response"),
                    "same_runtime_engine": runtime_engine == public_engine,
                    "same_conversation_plan": runtime_plan == public_plan,
                    "public_trace_source": (public_result.get("public_trace") or {}).get("source"),
                    "visible_response_source": (public_result.get("runtime_shadow") or {}).get("visible_response_source"),
                    "legacy_visible": bool(public_result.get("legacy_response") and public_result.get("legacy_response") == public_result.get("response")),
                    "narrative_response_composer": (public_diagnostic.get("narrative_response_composer") or {}),
                    "runtime_execution_engine": public_engine,
                }
            )
        scenario_results.append(
            {
                "id": scenario.id,
                "title": scenario.title,
                "turn_count": len(turns),
                "all_responses_equal": all(turn["same_response"] for turn in turns),
                "all_engines_equal": all(turn["same_runtime_engine"] for turn in turns),
                "all_plans_equal": all(turn["same_conversation_plan"] for turn in turns),
                "legacy_visible_count": sum(1 for turn in turns if turn["legacy_visible"]),
                "turns": turns,
            }
        )

    total_turns = sum(result["turn_count"] for result in scenario_results)
    response_matches = sum(1 for result in scenario_results for turn in result["turns"] if turn["same_response"])
    engine_matches = sum(1 for result in scenario_results for turn in result["turns"] if turn["same_runtime_engine"])
    plan_matches = sum(1 for result in scenario_results for turn in result["turns"] if turn["same_conversation_plan"])
    public_runtime_source = sum(
        1
        for result in scenario_results
        for turn in result["turns"]
        if turn["public_trace_source"] == "ACAOSRuntime"
    )
    runtime_response_source = sum(
        1
        for result in scenario_results
        for turn in result["turns"]
        if turn["visible_response_source"] == "runtime_response"
    )
    legacy_visible = sum(result["legacy_visible_count"] for result in scenario_results)

    return {
        "contract": "public_runtime_adapter_benchmark_result.v1",
        "benchmark": suite["benchmark"],
        "scenario_count": len(scenario_results),
        "turn_count": total_turns,
        "quality": {
            "response_equivalence_percentage": _percent(response_matches, total_turns),
            "runtime_engine_equivalence_percentage": _percent(engine_matches, total_turns),
            "conversation_plan_equivalence_percentage": _percent(plan_matches, total_turns),
            "public_runtime_source_percentage": _percent(public_runtime_source, total_turns),
            "runtime_response_source_percentage": _percent(runtime_response_source, total_turns),
            "legacy_visible_count": legacy_visible,
        },
        "scenarios": scenario_results,
    }


def load_operational_work_benchmark(
    path: str | Path | None = None,
) -> Dict[str, Any]:
    benchmark_path = Path(path or DEFAULT_OPERATIONAL_BENCHMARK_PATH)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    scenarios = [dict(item) for item in data.get("scenarios", [])]
    return {
        "contract": "operational_work_benchmark_suite.v1",
        "benchmark": data.get("benchmark", "aca_operational_work_benchmark.v1"),
        "description": data.get("description", ""),
        "domain": data.get("domain", "cross_domain_service_operations"),
        "path": str(benchmark_path),
        "scenario_count": len(scenarios),
        "turn_count": len(scenarios),
        "scenario_types": sorted({str(item.get("type") or "") for item in scenarios if item.get("type")}),
        "scenarios": scenarios,
    }


def run_operational_work_benchmark(
    path: str | Path | None = None,
    *,
    scenario_ids: Sequence[str] | None = None,
    max_scenarios: int | None = None,
    runtime_factory: Callable[[], Any] | None = None,
    plugin_root: str | Path = "plugins",
) -> Dict[str, Any]:
    """Run the operational shadow benchmark against the real ACA runtime."""

    if runtime_factory is None:
        from sdk.factory import build_galicia_runtime

        runtime_factory = build_galicia_runtime

    suite = load_operational_work_benchmark(path)
    scenarios = list(suite["scenarios"])
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario.get("id") in wanted]
    if max_scenarios is not None:
        scenarios = scenarios[:max_scenarios]

    plugin_manifests = _load_plugin_manifest_catalog(plugin_root)
    results = []
    for ordinal, scenario in enumerate(scenarios, start=1):
        runtime = runtime_factory()
        tool_contracts = _tool_contract_catalog(runtime)
        conversation_id = f"operational-benchmark:{ordinal}:{scenario.get('id')}"
        turns = list(scenario.get("turns") or [{"user": scenario.get("initial_message") or ""}])
        state = None
        for turn in turns:
            message = str(_mapping(turn).get("user") if isinstance(turn, Mapping) else turn)
            state = runtime.process(
                Event(
                    type="user_message",
                    payload=message,
                    metadata={"conversation_id": conversation_id},
                )
            )
        if state is None:
            continue
        state_snapshot = state.to_dict()
        mapped_work = map_operational_work(
            state_snapshot,
            plugin_manifests=plugin_manifests,
            tool_contracts=tool_contracts,
        )
        comparison = compare_operational_work_to_expected(mapped_work, scenario)
        results.append(
            {
                "contract": "operational_work_scenario_result.v1",
                "id": scenario.get("id"),
                "type": scenario.get("type"),
                "equivalence_group": scenario.get("equivalence_group"),
                "context": scenario.get("context"),
                "initial_message": scenario.get("initial_message"),
                "turns": turns,
                "expected": {
                    "operation": scenario.get("expected_operation"),
                    "category": scenario.get("expected_category"),
                    "outcome": scenario.get("expected_outcome"),
                    "do_not_ask": list(scenario.get("do_not_ask") or []),
                },
                "response": getattr(state, "response", None),
                "mapped_work": mapped_work,
                "comparison": comparison,
                "runtime": {
                    "selected_program": getattr(state, "selected_program", None),
                    "intent": getattr(state, "intent_match", None),
                    "runtime_execution_engine": _mapping((getattr(state, "facts", {}) or {}).get("runtime_execution_engine")),
                },
            }
        )

    aggregate = _aggregate_operational_results(results)
    turn_count = sum(len(result.get("turns") or []) for result in results)
    return {
        "contract": "operational_work_benchmark_result.v1",
        "benchmark": suite["benchmark"],
        "description": suite["description"],
        "domain": suite["domain"],
        "source_path": suite["path"],
        "scenario_count": len(results),
        "turn_count": turn_count,
        "coverage": {
            "scenario_types": suite["scenario_types"],
            "scenario_count": len(results),
            "turn_count": turn_count,
            "plugin_manifest_count": len(plugin_manifests),
        },
        "quality": aggregate["quality"],
        "architecture": aggregate["architecture"],
        "errors": aggregate["errors"],
        "scenarios": results,
    }


def render_operational_work_benchmark_report(result: Mapping[str, Any]) -> str:
    quality = dict(result.get("quality") or {})
    architecture = dict(result.get("architecture") or {})
    errors = dict(result.get("errors") or {})
    lines = [
        "# ACA Operational Work Benchmark",
        "",
        f"- Benchmark: `{result.get('benchmark')}`",
        f"- Scenarios: {result.get('scenario_count', 0)}",
        f"- Turns: {result.get('turn_count', 0)}",
        f"- Work identified: {quality.get('work_identified_percentage', 0)}%",
        f"- Correct operation selection: {quality.get('correct_operation_selection_percentage', 0)}%",
        f"- Outcome match: {quality.get('outcome_match_percentage', 0)}%",
        f"- Impossible work suggested: {quality.get('impossible_work_percentage', 0)}%",
        "",
        "## Quality",
        "",
        f"- Useful work turns: {quality.get('useful_work_turns', 0)}",
        f"- Operational value per turn: {quality.get('operational_value_per_turn', 0)}",
        f"- False positives: {quality.get('false_positive_count', 0)}",
        f"- Work confused with conversation: {quality.get('conversation_work_confusion_count', 0)}",
        f"- Equivalent group stability: {quality.get('equivalent_group_stability_percentage', 0)}%",
        "",
        "## Architecture",
        "",
        f"- Mapper mode: {architecture.get('mapper_mode')}",
        f"- Runtime mutations: {architecture.get('runtime_mutations')}",
        f"- Response changes: {architecture.get('response_changes')}",
        f"- Components observed: {', '.join(architecture.get('observed_components') or []) or 'none'}",
        "",
        "## Errors",
        "",
    ]
    counts = errors.get("counts") or {}
    if counts:
        for name, count in sorted(counts.items()):
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none detected by operational shadow rules")
    lines.extend(["", "## Scenario Summary", ""])
    for scenario in result.get("scenarios") or []:
        comparison = dict(scenario.get("comparison") or {})
        selected = dict((scenario.get("mapped_work") or {}).get("selected_work") or {})
        lines.append(
            f"- `{scenario.get('id')}`: operation={selected.get('operation')}, "
            f"outcome={selected.get('expected_outcome')}, "
            f"match={comparison.get('operation_match')}/{comparison.get('outcome_match')}"
        )
    lines.append("")
    return "\n".join(lines)


def load_operational_governance_benchmark(
    path: str | Path | None = None,
) -> Dict[str, Any]:
    benchmark_path = Path(path or DEFAULT_OPERATIONAL_GOVERNANCE_BENCHMARK_PATH)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    scenarios = [dict(item) for item in data.get("scenarios", [])]
    return {
        "contract": "operational_governance_benchmark_suite.v1",
        "benchmark": data.get("benchmark", "aca_operational_governance_benchmark.v1"),
        "description": data.get("description", ""),
        "domain": data.get("domain", "operational_governance"),
        "path": str(benchmark_path),
        "scenario_count": len(scenarios),
        "scenario_types": sorted({str(item.get("type") or "") for item in scenarios if item.get("type")}),
        "scenarios": scenarios,
    }


def run_operational_governance_benchmark(
    path: str | Path | None = None,
    *,
    scenario_ids: Sequence[str] | None = None,
    max_scenarios: int | None = None,
    runtime_factory: Callable[[], Any] | None = None,
    plugin_root: str | Path = "plugins",
) -> Dict[str, Any]:
    """Run the operational governance gate in shadow mode."""

    if runtime_factory is None:
        from sdk.factory import build_galicia_runtime

        runtime_factory = build_galicia_runtime

    suite = load_operational_governance_benchmark(path)
    scenarios = list(suite["scenarios"])
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario.get("id") in wanted]
    if max_scenarios is not None:
        scenarios = scenarios[:max_scenarios]

    plugin_manifests = _load_plugin_manifest_catalog(plugin_root)
    results = []
    for ordinal, scenario in enumerate(scenarios, start=1):
        scenario_manifests = list(scenario.get("plugin_manifests") or plugin_manifests)
        runtime = runtime_factory()
        runtime_tool_contracts = _tool_contract_catalog(runtime)
        scenario_tool_contracts = _mapping(scenario.get("tool_contracts"))
        tool_contracts = scenario_tool_contracts if scenario_tool_contracts else runtime_tool_contracts
        mapped_work = _mapped_work_for_governance_scenario(
            scenario=scenario,
            runtime=runtime,
            ordinal=ordinal,
            plugin_manifests=scenario_manifests,
            tool_contracts=tool_contracts,
        )
        facts = _mapping(_mapping(mapped_work.get("source_snapshot")).get("facts"))
        assessment = assess_operational_governance(
            mapped_work,
            plugin_manifests=scenario_manifests,
            tool_contracts=tool_contracts,
            policy=_mapping(scenario.get("policy")) or _mapping(facts.get("runtime_execution_authority")).get("policy_evaluation", {}),
            execution_plan=_mapping(scenario.get("execution_plan")) or _mapping(facts.get("zero_cost_execution_plan")),
            runtime_outcomes=list(scenario.get("runtime_outcomes") or facts.get("execution_step_outcomes") or []),
            governance_context=_mapping(scenario.get("governance_context")),
        )
        comparison = compare_governance_to_expected(
            assessment,
            _mapping(scenario.get("expected_governance")),
        )
        results.append(
            {
                "contract": "operational_governance_scenario_result.v1",
                "id": scenario.get("id"),
                "type": scenario.get("type"),
                "context": scenario.get("context"),
                "input_source": "runtime" if scenario.get("initial_message") or scenario.get("turns") else "candidate_work_fixture",
                "mapped_work": mapped_work,
                "assessment": assessment,
                "comparison": comparison,
            }
        )

    aggregate = _aggregate_operational_governance_results(results)
    return {
        "contract": "operational_governance_benchmark_result.v1",
        "benchmark": suite["benchmark"],
        "description": suite["description"],
        "domain": suite["domain"],
        "source_path": suite["path"],
        "scenario_count": len(results),
        "coverage": {
            "scenario_types": suite["scenario_types"],
            "scenario_count": len(results),
            "plugin_manifest_count": len(plugin_manifests),
        },
        "quality": aggregate["quality"],
        "readiness": aggregate["readiness"],
        "errors": aggregate["errors"],
        "scenarios": results,
    }


def render_operational_governance_benchmark_report(result: Mapping[str, Any]) -> str:
    quality = dict(result.get("quality") or {})
    readiness = dict(result.get("readiness") or {})
    errors = dict(result.get("errors") or {})
    lines = [
        "# ACA Operational Governance Benchmark",
        "",
        f"- Benchmark: `{result.get('benchmark')}`",
        f"- Scenarios: {result.get('scenario_count', 0)}",
        f"- Governance accuracy: {quality.get('governance_accuracy_percentage', 0)}%",
        f"- Unsafe execution detection: {quality.get('unsafe_execution_detection_percentage', 0)}%",
        f"- Missing evidence detection: {quality.get('missing_evidence_detection_percentage', 0)}%",
        f"- Confirmation requirement accuracy: {quality.get('confirmation_requirement_accuracy_percentage', 0)}%",
        f"- Human approval accuracy: {quality.get('human_approval_accuracy_percentage', 0)}%",
        f"- Tool availability accuracy: {quality.get('tool_availability_accuracy_percentage', 0)}%",
        f"- Idempotency detection: {quality.get('idempotency_detection_percentage', 0)}%",
        "",
        "## Readiness",
        "",
        f"- Automatically executable: {readiness.get('automatic_execution_count', 0)}",
        f"- Requires confirmation: {readiness.get('requires_confirmation_count', 0)}",
        f"- Requires human approval: {readiness.get('requires_human_approval_count', 0)}",
        f"- Manual only: {readiness.get('manual_only_count', 0)}",
        f"- Depends on real tool contract: {readiness.get('tool_contract_dependent_count', 0)}",
        f"- Immediately enabled: {readiness.get('immediate_enablement_percentage', 0)}%",
        "",
        "## Errors",
        "",
    ]
    counts = errors.get("counts") or {}
    if counts:
        for name, count in sorted(counts.items()):
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none detected by operational governance rules")
    lines.extend(["", "## Scenario Summary", ""])
    for scenario in result.get("scenarios") or []:
        assessment = _mapping(scenario.get("assessment"))
        selected = _mapping(assessment.get("selected_work"))
        risk = _mapping(assessment.get("risk"))
        lines.append(
            f"- `{scenario.get('id')}`: operation={selected.get('operation')}, "
            f"risk={risk.get('level')}, allowed={assessment.get('execution_allowed')}, "
            f"recommendation={assessment.get('recommended_execution')}"
        )
    lines.append("")
    return "\n".join(lines)


def load_operational_audit_ledger_benchmark(
    path: str | Path | None = None,
) -> Dict[str, Any]:
    benchmark_path = Path(path or DEFAULT_OPERATIONAL_AUDIT_LEDGER_BENCHMARK_PATH)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    scenarios = [dict(item) for item in data.get("scenarios", [])]
    return {
        "contract": "operational_audit_ledger_benchmark_suite.v1",
        "benchmark": data.get("benchmark", "aca_operational_audit_ledger_benchmark.v1"),
        "description": data.get("description", ""),
        "domain": data.get("domain", "operational_audit"),
        "path": str(benchmark_path),
        "scenario_count": len(scenarios),
        "scenario_types": sorted({str(item.get("type") or "") for item in scenarios if item.get("type")}),
        "scenarios": scenarios,
    }


def run_operational_audit_ledger_benchmark(
    path: str | Path | None = None,
    *,
    scenario_ids: Sequence[str] | None = None,
    max_scenarios: int | None = None,
    runtime_factory: Callable[[], Any] | None = None,
    plugin_root: str | Path = "plugins",
) -> Dict[str, Any]:
    """Run the operational audit ledger in shadow mode."""

    if runtime_factory is None:
        from sdk.factory import build_galicia_runtime

        runtime_factory = build_galicia_runtime

    suite = load_operational_audit_ledger_benchmark(path)
    scenarios = list(suite["scenarios"])
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario.get("id") in wanted]
    if max_scenarios is not None:
        scenarios = scenarios[:max_scenarios]

    plugin_manifests = _load_plugin_manifest_catalog(plugin_root)
    results = []
    for ordinal, scenario in enumerate(scenarios, start=1):
        scenario_manifests = list(scenario.get("plugin_manifests") or plugin_manifests)
        runtime = runtime_factory()
        runtime_tool_contracts = _tool_contract_catalog(runtime)
        scenario_tool_contracts = _mapping(scenario.get("tool_contracts"))
        tool_contracts = scenario_tool_contracts if scenario_tool_contracts else runtime_tool_contracts
        mapped_work = _mapped_work_for_governance_scenario(
            scenario=scenario,
            runtime=runtime,
            ordinal=ordinal,
            plugin_manifests=scenario_manifests,
            tool_contracts=tool_contracts,
        )
        facts = _mapping(_mapping(mapped_work.get("source_snapshot")).get("facts"))
        governance_context = _mapping(scenario.get("governance_context"))
        assessment = assess_operational_governance(
            mapped_work,
            plugin_manifests=scenario_manifests,
            tool_contracts=tool_contracts,
            policy=_mapping(scenario.get("policy")) or _mapping(facts.get("runtime_execution_authority")).get("policy_evaluation", {}),
            execution_plan=_mapping(scenario.get("execution_plan")) or _mapping(facts.get("zero_cost_execution_plan")),
            runtime_outcomes=list(scenario.get("runtime_outcomes") or facts.get("execution_step_outcomes") or []),
            governance_context=governance_context,
        )
        ledger_context = {**governance_context, **_mapping(scenario.get("ledger_context"))}
        ledger_record = project_operational_audit_ledger(
            mapped_work,
            assessment,
            tool_contracts=tool_contracts,
            execution_plan=_mapping(scenario.get("execution_plan")) or _mapping(facts.get("zero_cost_execution_plan")),
            runtime_outcomes=list(scenario.get("runtime_outcomes") or facts.get("execution_step_outcomes") or []),
            ledger_context=ledger_context,
        )
        comparison = compare_ledger_to_expected(
            ledger_record,
            _mapping(scenario.get("expected_ledger")),
        )
        results.append(
            {
                "contract": "operational_audit_ledger_scenario_result.v1",
                "id": scenario.get("id"),
                "type": scenario.get("type"),
                "context": scenario.get("context"),
                "mapped_work": mapped_work,
                "governance_assessment": assessment,
                "ledger_record": ledger_record,
                "comparison": comparison,
            }
        )

    aggregate = _aggregate_operational_audit_ledger_results(results)
    return {
        "contract": "operational_audit_ledger_benchmark_result.v1",
        "benchmark": suite["benchmark"],
        "description": suite["description"],
        "domain": suite["domain"],
        "source_path": suite["path"],
        "scenario_count": len(results),
        "coverage": {
            "scenario_types": suite["scenario_types"],
            "scenario_count": len(results),
            "plugin_manifest_count": len(plugin_manifests),
        },
        "quality": aggregate["quality"],
        "readiness": aggregate["readiness"],
        "errors": aggregate["errors"],
        "scenarios": results,
    }


def render_operational_audit_ledger_benchmark_report(result: Mapping[str, Any]) -> str:
    quality = dict(result.get("quality") or {})
    readiness = dict(result.get("readiness") or {})
    errors = dict(result.get("errors") or {})
    lines = [
        "# ACA Operational Audit Ledger Benchmark",
        "",
        f"- Benchmark: `{result.get('benchmark')}`",
        f"- Scenarios: {result.get('scenario_count', 0)}",
        f"- Ledger completeness: {quality.get('ledger_completeness_percentage', 0)}%",
        f"- Audit trace completeness: {quality.get('audit_trace_completeness_percentage', 0)}%",
        f"- Idempotency coverage: {quality.get('idempotency_coverage_percentage', 0)}%",
        f"- Receipt coverage: {quality.get('receipt_coverage_percentage', 0)}%",
        f"- Compensation coverage: {quality.get('compensation_coverage_percentage', 0)}%",
        f"- Replay safety: {quality.get('replay_safety_percentage', 0)}%",
        f"- Duplicate detection accuracy: {quality.get('duplicate_detection_accuracy_percentage', 0)}%",
        "",
        "## Readiness",
        "",
        f"- Reconstructable operations: {readiness.get('reconstructable_operation_count', 0)}",
        f"- Durable persistence still required: {readiness.get('requires_durable_persistence_count', 0)}",
        f"- Conceptual completeness: {readiness.get('conceptual_completeness_percentage', 0)}%",
        "",
        "## Errors",
        "",
    ]
    counts = errors.get("counts") or {}
    if counts:
        for name, count in sorted(counts.items()):
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none detected by operational audit ledger rules")
    lines.extend(["", "## Scenario Summary", ""])
    for scenario in result.get("scenarios") or []:
        ledger = _mapping(scenario.get("ledger_record"))
        selected = _mapping(ledger.get("selected_work"))
        execution = _mapping(ledger.get("execution_status"))
        lines.append(
            f"- `{scenario.get('id')}`: operation={selected.get('operation')}, "
            f"status={execution.get('state')}, complete={_mapping(ledger.get('completeness')).get('complete')}"
        )
    lines.append("")
    return "\n".join(lines)


def load_operational_dry_run_benchmark(
    path: str | Path | None = None,
) -> Dict[str, Any]:
    benchmark_path = Path(path or DEFAULT_OPERATIONAL_DRY_RUN_BENCHMARK_PATH)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    scenarios = [dict(item) for item in data.get("scenarios", [])]
    return {
        "contract": "operational_dry_run_benchmark_suite.v1",
        "benchmark": data.get("benchmark", "aca_operational_dry_run_benchmark.v1"),
        "description": data.get("description", ""),
        "domain": data.get("domain", "operational_integration"),
        "path": str(benchmark_path),
        "scenario_count": len(scenarios),
        "scenario_types": sorted({str(item.get("type") or "") for item in scenarios if item.get("type")}),
        "tool": data.get("tool", "handoff_package"),
        "operation": data.get("operation", "prepare_handoff"),
        "scenarios": scenarios,
    }


def run_operational_dry_run_benchmark(
    path: str | Path | None = None,
    *,
    scenario_ids: Sequence[str] | None = None,
    max_scenarios: int | None = None,
    runtime_factory: Callable[[], Any] | None = None,
    plugin_root: str | Path = "plugins",
) -> Dict[str, Any]:
    """Run the first real operational tool integration in dry-run mode."""

    if runtime_factory is None:
        from sdk.factory import build_galicia_runtime

        runtime_factory = build_galicia_runtime

    suite = load_operational_dry_run_benchmark(path)
    scenarios = list(suite["scenarios"])
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario.get("id") in wanted]
    if max_scenarios is not None:
        scenarios = scenarios[:max_scenarios]

    plugin_manifests = _load_plugin_manifest_catalog(plugin_root)
    results = []
    for ordinal, scenario in enumerate(scenarios, start=1):
        runtime = runtime_factory()
        _register_operational_dry_run_tools(runtime)
        tool_contracts = _tool_contract_catalog(runtime)
        conversation_id = f"operational-dry-run:{ordinal}:{scenario.get('id')}"
        turns = list(scenario.get("turns") or [{"user": scenario.get("initial_message") or ""}])
        state = None
        for turn in turns:
            message = str(_mapping(turn).get("user") if isinstance(turn, Mapping) else turn)
            state = runtime.process(
                Event(
                    type="user_message",
                    payload=message,
                    metadata={"conversation_id": conversation_id},
                )
            )
        if state is None:
            continue
        state_snapshot = state.to_dict()
        mapped_work = map_operational_work(
            state_snapshot,
            plugin_manifests=plugin_manifests,
            tool_contracts=tool_contracts,
        )
        facts = _mapping(state_snapshot.get("facts"))
        execution_plan = _mapping(facts.get("zero_cost_execution_plan"))
        runtime_outcomes = list(facts.get("execution_step_outcomes") or [])
        policy = _mapping(facts.get("runtime_execution_authority")).get("policy_evaluation", {})
        governance_context = _mapping(scenario.get("governance_context"))
        assessment = assess_operational_governance(
            mapped_work,
            plugin_manifests=plugin_manifests,
            tool_contracts=tool_contracts,
            policy=_mapping(policy),
            execution_plan=execution_plan,
            runtime_outcomes=runtime_outcomes,
            governance_context=governance_context,
        )
        ledger_context = {
            "conversation_id": conversation_id,
            **governance_context,
            **_mapping(scenario.get("ledger_context")),
        }
        ledger_record = project_operational_audit_ledger(
            mapped_work,
            assessment,
            tool_contracts=tool_contracts,
            execution_plan=execution_plan,
            runtime_outcomes=runtime_outcomes,
            ledger_context=ledger_context,
        )
        tool_request = _operational_dry_run_tool_request(
            scenario=scenario,
            conversation_id=conversation_id,
            mapped_work=mapped_work,
            governance_assessment=assessment,
            ledger_record=ledger_record,
        )
        dry_run_result = runtime.tool_engine.execute(
            tool_request,
            ToolExecutionContext(
                mode=ToolExecutionMode.DRY_RUN,
                origin="operational_dry_run_benchmark",
                execution_plan=execution_plan,
                runtime_engine="runtime_executor",
                simulation={"scenario_id": str(scenario.get("id") or "")},
            ),
        )
        replay_result = runtime.tool_engine.execute(
            tool_request,
            ToolExecutionContext(
                mode=ToolExecutionMode.REPLAY,
                origin="operational_dry_run_benchmark",
                execution_plan=execution_plan,
                runtime_engine="runtime_executor",
                replay_evidence=dry_run_result.evidence,
                simulation={"scenario_id": str(scenario.get("id") or "")},
            ),
        )
        comparison = _compare_operational_dry_run(
            scenario=scenario,
            mapped_work=mapped_work,
            governance_assessment=assessment,
            ledger_record=ledger_record,
            dry_run_result=dry_run_result,
            replay_result=replay_result,
        )
        results.append(
            {
                "contract": "operational_dry_run_scenario_result.v1",
                "id": scenario.get("id"),
                "type": scenario.get("type"),
                "context": scenario.get("context"),
                "turns": turns,
                "expected": {
                    "operation": scenario.get("expected_operation"),
                    "tool": scenario.get("expected_tool"),
                    "receipt_status": scenario.get("expected_receipt_status"),
                },
                "visible_response": getattr(state, "response", None),
                "mapped_work": mapped_work,
                "governance_assessment": assessment,
                "ledger_record": ledger_record,
                "tool_execution": {
                    "dry_run": dry_run_result.execution,
                    "replay": replay_result.execution,
                },
                "tool_evidence": dry_run_result.evidence,
                "replay_evidence": replay_result.evidence,
                "comparison": comparison,
            }
        )

    aggregate = _aggregate_operational_dry_run_results(results)
    return {
        "contract": "operational_dry_run_benchmark_result.v1",
        "benchmark": suite["benchmark"],
        "description": suite["description"],
        "domain": suite["domain"],
        "source_path": suite["path"],
        "scenario_count": len(results),
        "coverage": {
            "scenario_types": suite["scenario_types"],
            "scenario_count": len(results),
            "plugin_manifest_count": len(plugin_manifests),
            "tool": suite["tool"],
            "operation": suite["operation"],
        },
        "quality": aggregate["quality"],
        "architecture": aggregate["architecture"],
        "errors": aggregate["errors"],
        "scenarios": results,
    }


def render_operational_dry_run_benchmark_report(result: Mapping[str, Any]) -> str:
    quality = dict(result.get("quality") or {})
    architecture = dict(result.get("architecture") or {})
    errors = dict(result.get("errors") or {})
    lines = [
        "# ACA Operational Dry Run Benchmark",
        "",
        f"- Benchmark: `{result.get('benchmark')}`",
        f"- Scenarios: {result.get('scenario_count', 0)}",
        f"- End-to-end success: {quality.get('end_to_end_success_percentage', 0)}%",
        f"- Candidate/tool coherence: {quality.get('candidate_tool_coherence_percentage', 0)}%",
        f"- Governance pass: {quality.get('governance_pass_percentage', 0)}%",
        f"- Ledger completeness: {quality.get('ledger_completeness_percentage', 0)}%",
        f"- Receipt generated: {quality.get('receipt_generated_percentage', 0)}%",
        f"- Side-effect free: {quality.get('side_effect_free_percentage', 0)}%",
        f"- Replay consistency: {quality.get('replay_consistency_percentage', 0)}%",
        f"- Idempotency coverage: {quality.get('idempotency_coverage_percentage', 0)}%",
        "",
        "## Architecture",
        "",
        f"- Runtime mutations: {architecture.get('runtime_mutations')}",
        f"- Visible response changes: {architecture.get('visible_response_changes')}",
        f"- Tool execution mode: {architecture.get('tool_execution_mode')}",
        f"- Operational tool: {architecture.get('tool')}",
        "",
        "## Errors",
        "",
    ]
    counts = errors.get("counts") or {}
    if counts:
        for name, count in sorted(counts.items()):
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none detected by operational dry-run rules")
    lines.extend(["", "## Scenario Summary", ""])
    for scenario in result.get("scenarios") or []:
        selected = _mapping(_mapping(scenario.get("mapped_work")).get("selected_work"))
        receipt = _mapping(_mapping(_mapping(scenario.get("tool_evidence")).get("projected_receipt")))
        comparison = _mapping(scenario.get("comparison"))
        lines.append(
            f"- `{scenario.get('id')}`: operation={selected.get('operation')}, "
            f"receipt={receipt.get('status')}, passed={comparison.get('passed')}"
        )
    lines.append("")
    return "\n".join(lines)


def load_operational_production_benchmark(
    path: str | Path | None = None,
) -> Dict[str, Any]:
    benchmark_path = Path(path or DEFAULT_OPERATIONAL_PRODUCTION_BENCHMARK_PATH)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    scenarios = [dict(item) for item in data.get("scenarios", [])]
    return {
        "contract": "operational_production_benchmark_suite.v1",
        "benchmark": data.get("benchmark", "aca_operational_production_benchmark.v1"),
        "description": data.get("description", ""),
        "domain": data.get("domain", "operational_production_integration"),
        "path": str(benchmark_path),
        "scenario_count": len(scenarios),
        "scenario_types": sorted({str(item.get("type") or "") for item in scenarios if item.get("type")}),
        "tool": data.get("tool", "handoff_package"),
        "operation": data.get("operation", "prepare_handoff"),
        "scenarios": scenarios,
    }


def run_operational_production_benchmark(
    path: str | Path | None = None,
    *,
    scenario_ids: Sequence[str] | None = None,
    max_scenarios: int | None = None,
    runtime_factory: Callable[[], Any] | None = None,
    plugin_root: str | Path = "plugins",
    storage_root: str | Path | None = None,
) -> Dict[str, Any]:
    """Run the first real operational tool integration with durable ledger persistence."""

    if runtime_factory is None:
        from sdk.factory import build_galicia_runtime

        runtime_factory = build_galicia_runtime

    suite = load_operational_production_benchmark(path)
    scenarios = list(suite["scenarios"])
    if scenario_ids:
        wanted = set(scenario_ids)
        scenarios = [scenario for scenario in scenarios if scenario.get("id") in wanted]
    if max_scenarios is not None:
        scenarios = scenarios[:max_scenarios]

    run_root = Path(storage_root) if storage_root else ROOT / ".aca" / "operational_production_benchmark" / str(uuid4())
    plugin_manifests = _load_plugin_manifest_catalog(plugin_root)
    results = []
    for ordinal, scenario in enumerate(scenarios, start=1):
        scenario_root = run_root / str(scenario.get("id") or f"scenario-{ordinal}")
        package_store_path = scenario_root / "handoff_packages.jsonl"
        ledger_store = JsonlOperationalAuditLedgerStore(scenario_root / "operational_ledger.jsonl")
        runtime = runtime_factory()
        _register_operational_production_tools(runtime, package_store_path=package_store_path)
        tool_contracts = _tool_contract_catalog(runtime)
        conversation_id = f"operational-production:{ordinal}:{scenario.get('id')}"
        turns = list(scenario.get("turns") or [{"user": scenario.get("initial_message") or ""}])
        state = None
        for turn in turns:
            message = str(_mapping(turn).get("user") if isinstance(turn, Mapping) else turn)
            state = runtime.process(
                Event(
                    type="user_message",
                    payload=message,
                    metadata={"conversation_id": conversation_id},
                )
            )
        if state is None:
            continue
        attempts = list(scenario.get("attempts") or [{}])
        attempt_results = []
        replay_result = None
        for attempt_index, attempt in enumerate(attempts, start=1):
            attempt_spec = _mapping(attempt)
            state_snapshot = state.to_dict()
            mapped_work = map_operational_work(
                state_snapshot,
                plugin_manifests=plugin_manifests,
                tool_contracts=tool_contracts,
            )
            facts = _mapping(state_snapshot.get("facts"))
            execution_plan = _mapping(facts.get("zero_cost_execution_plan"))
            runtime_outcomes = list(facts.get("execution_step_outcomes") or [])
            policy = _mapping(facts.get("runtime_execution_authority")).get("policy_evaluation", {})
            idempotency_key = str(attempt_spec.get("idempotency_key") or scenario.get("idempotency_key") or _stable_benchmark_idempotency(conversation_id, scenario))
            governance_context = {
                "available_evidence": ["candidate_evidence", "case_state_evidence", "operation_evidence"],
                "permissions": {"execute:prepare_handoff": True},
                "idempotency_key": idempotency_key,
                **_mapping(scenario.get("governance_context")),
                **_mapping(attempt_spec.get("governance_context")),
            }
            assessment = assess_operational_governance(
                mapped_work,
                plugin_manifests=plugin_manifests,
                tool_contracts=tool_contracts,
                policy=_mapping(policy),
                execution_plan=execution_plan,
                runtime_outcomes=runtime_outcomes,
                governance_context=governance_context,
            )
            ledger_context = {
                "conversation_id": conversation_id,
                "previous_ledger_records": ledger_store.records(),
                **governance_context,
                **_mapping(scenario.get("ledger_context")),
                **_mapping(attempt_spec.get("ledger_context")),
            }
            ledger_record = project_operational_audit_ledger(
                mapped_work,
                assessment,
                tool_contracts=tool_contracts,
                execution_plan=execution_plan,
                runtime_outcomes=runtime_outcomes,
                ledger_context=ledger_context,
            )
            if not assessment.get("execution_allowed"):
                finalized = finalize_operational_audit_ledger(
                    ledger_record,
                    tool_result=_blocked_tool_result(scenario.get("expected_tool") or "handoff_package", reason="governance_blocked"),
                )
                persisted = ledger_store.persist(finalized)
                tool_result = _blocked_tool_result(scenario.get("expected_tool") or "handoff_package", reason="governance_blocked")
            else:
                request = _operational_production_tool_request(
                    scenario=scenario,
                    attempt=attempt_spec,
                    conversation_id=conversation_id,
                    idempotency_key=idempotency_key,
                    mapped_work=mapped_work,
                    governance_assessment=assessment,
                    ledger_record=ledger_record,
                )
                tool_result = runtime.tool_engine.execute(
                    request,
                    ToolExecutionContext(
                        mode=ToolExecutionMode.OFFICIAL,
                        origin="operational_production_benchmark",
                        execution_plan=execution_plan,
                        runtime_engine="runtime_executor",
                        permissions=dict(governance_context.get("permissions") or {}),
                        simulation={"scenario_id": str(scenario.get("id") or ""), "attempt": attempt_index},
                    ),
                )
                finalized = finalize_operational_audit_ledger(ledger_record, tool_result=tool_result)
                persisted = ledger_store.persist(finalized)
            attempt_results.append(
                {
                    "attempt": attempt_index,
                    "mapped_work": mapped_work,
                    "governance_assessment": assessment,
                    "ledger_record": persisted,
                    "tool_execution": getattr(tool_result, "execution", {}),
                    "tool_evidence": getattr(tool_result, "evidence", {}),
                    "tool_success": bool(getattr(tool_result, "success", False)),
                    "tool_error": getattr(tool_result, "error", None),
                }
            )
        final_attempt = attempt_results[-1] if attempt_results else {}
        final_evidence = _mapping(final_attempt.get("tool_evidence"))
        final_receipt = _mapping(final_evidence.get("external_receipt") or final_evidence.get("projected_receipt"))
        if bool(scenario.get("run_replay", True)) and final_receipt.get("receipt_id"):
            runtime = runtime_factory()
            _register_operational_production_tools(runtime, package_store_path=package_store_path)
            replay_request = ToolRequest(
                tool_name=str(scenario.get("expected_tool") or "handoff_package"),
                intent="prepare_handoff_package",
                payload={"idempotency_key": final_receipt.get("idempotency_key")},
            )
            replay_result = runtime.tool_engine.execute(
                replay_request,
                ToolExecutionContext(
                    mode=ToolExecutionMode.REPLAY,
                    origin="operational_production_benchmark",
                    runtime_engine="runtime_executor",
                    replay_evidence=final_evidence,
                ),
            )
        comparison = _compare_operational_production(
            scenario=scenario,
            attempts=attempt_results,
            replay_result=replay_result,
            package_store_path=package_store_path,
            ledger_store=ledger_store,
        )
        results.append(
            {
                "contract": "operational_production_scenario_result.v1",
                "id": scenario.get("id"),
                "type": scenario.get("type"),
                "context": scenario.get("context"),
                "turns": turns,
                "visible_response": getattr(state, "response", None),
                "attempts": attempt_results,
                "replay": replay_result.to_dict() if hasattr(replay_result, "to_dict") else _tool_result_to_dict(replay_result),
                "comparison": comparison,
            }
        )

    aggregate = _aggregate_operational_production_results(results)
    return {
        "contract": "operational_production_benchmark_result.v1",
        "benchmark": suite["benchmark"],
        "description": suite["description"],
        "domain": suite["domain"],
        "source_path": suite["path"],
        "scenario_count": len(results),
        "storage_root": str(run_root),
        "coverage": {
            "scenario_types": suite["scenario_types"],
            "scenario_count": len(results),
            "plugin_manifest_count": len(plugin_manifests),
            "tool": suite["tool"],
            "operation": suite["operation"],
        },
        "quality": aggregate["quality"],
        "architecture": aggregate["architecture"],
        "errors": aggregate["errors"],
        "scenarios": results,
    }


def render_operational_production_benchmark_report(result: Mapping[str, Any]) -> str:
    quality = dict(result.get("quality") or {})
    architecture = dict(result.get("architecture") or {})
    errors = dict(result.get("errors") or {})
    lines = [
        "# ACA Operational Production Benchmark",
        "",
        f"- Benchmark: `{result.get('benchmark')}`",
        f"- Scenarios: {result.get('scenario_count', 0)}",
        f"- Real execution: {quality.get('real_execution_percentage', 0)}%",
        f"- Ledger persistence: {quality.get('ledger_persistence_percentage', 0)}%",
        f"- Receipt coverage: {quality.get('receipt_coverage_percentage', 0)}%",
        f"- Replay consistency: {quality.get('replay_consistency_percentage', 0)}%",
        f"- Idempotency accuracy: {quality.get('idempotency_accuracy_percentage', 0)}%",
        f"- Failure handling: {quality.get('failure_handling_percentage', 0)}%",
        f"- Ledger consistency: {quality.get('ledger_consistency_percentage', 0)}%",
        "",
        "## Architecture",
        "",
        f"- Runtime redesigned: {architecture.get('runtime_redesigned')}",
        f"- Conversation contracts modified: {architecture.get('conversation_contracts_modified')}",
        f"- Tool execution mode: {architecture.get('tool_execution_mode')}",
        f"- Durable ledger: {architecture.get('durable_ledger')}",
        f"- Operational tool: {architecture.get('tool')}",
        "",
        "## Errors",
        "",
    ]
    counts = errors.get("counts") or {}
    if counts:
        for name, count in sorted(counts.items()):
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none detected by operational production rules")
    lines.extend(["", "## Scenario Summary", ""])
    for scenario in result.get("scenarios") or []:
        comparison = _mapping(scenario.get("comparison"))
        final_attempt = _mapping((scenario.get("attempts") or [{}])[-1])
        ledger = _mapping(final_attempt.get("ledger_record"))
        execution = _mapping(ledger.get("execution_status"))
        lines.append(
            f"- `{scenario.get('id')}`: state={execution.get('state')}, "
            f"persisted={ledger.get('persistent')}, passed={comparison.get('passed')}"
        )
    lines.append("")
    return "\n".join(lines)


def load_operational_real_world_benchmark(
    path: str | Path | None = None,
) -> Dict[str, Any]:
    benchmark_path = Path(path or DEFAULT_OPERATIONAL_REAL_WORLD_BENCHMARK_PATH)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))
    conversations = [dict(item) for item in data.get("conversations", [])]
    return {
        "contract": "operational_real_world_benchmark_suite.v1",
        "benchmark": data.get("benchmark", "aca_operational_real_world_benchmark.v1"),
        "description": data.get("description", ""),
        "domain": data.get("domain", "real_world_service_conversations"),
        "path": str(benchmark_path),
        "conversation_count": len(conversations),
        "turn_count": sum(len(conversation.get("turns") or []) for conversation in conversations),
        "sources": sorted({str(item.get("source") or "") for item in conversations if item.get("source")}),
        "conversations": conversations,
    }


def run_operational_real_world_benchmark(
    path: str | Path | None = None,
    *,
    conversation_ids: Sequence[str] | None = None,
    max_conversations: int | None = None,
    runtime_factory: Callable[[], Any] | None = None,
    plugin_root: str | Path = "plugins",
) -> Dict[str, Any]:
    """Validate Operational Work Mapping against non-ideal multi-turn conversations."""

    if runtime_factory is None:
        from sdk.factory import build_galicia_runtime

        runtime_factory = build_galicia_runtime

    suite = load_operational_real_world_benchmark(path)
    conversations = list(suite["conversations"])
    if conversation_ids:
        wanted = set(conversation_ids)
        conversations = [conversation for conversation in conversations if conversation.get("id") in wanted]
    if max_conversations is not None:
        conversations = conversations[:max_conversations]

    plugin_manifests = _load_plugin_manifest_catalog(plugin_root)
    results = []
    for ordinal, conversation in enumerate(conversations, start=1):
        runtime = runtime_factory()
        tool_contracts = _tool_contract_catalog(runtime)
        conversation_id = f"operational-real-world:{ordinal}:{conversation.get('id')}"
        turn_results = []
        previous_operation = ""
        previous_operations: list[str] = []
        previous_candidate_operations: list[str] = []
        for turn_index, turn in enumerate(conversation.get("turns") or [], start=1):
            turn_spec = _mapping(turn)
            state = runtime.process(
                Event(
                    type="user_message",
                    payload=str(turn_spec.get("user") or ""),
                    metadata={"conversation_id": conversation_id},
                )
            )
            mapped_work = map_operational_work(
                state.to_dict(),
                plugin_manifests=plugin_manifests,
                tool_contracts=tool_contracts,
            )
            comparison = compare_operational_work_to_expected(mapped_work, turn_spec)
            selected = _mapping(mapped_work.get("selected_work"))
            operation = str(selected.get("operation") or "")
            actual_transition = _work_transition(
                operation=operation,
                previous_operation=previous_operation,
                previous_operations=previous_operations,
            )
            expected_transition = str(turn_spec.get("expected_transition") or "")
            transition_match = _transition_matches(
                expected=expected_transition,
                actual=actual_transition,
                operation=operation,
                previous_operation=previous_operation,
            )
            secondary_expected = [str(item) for item in turn_spec.get("expected_secondary_operations") or []]
            candidate_work = [
                _mapping(candidate)
                for candidate in mapped_work.get("candidate_work") or []
            ]
            candidate_operations = [
                str(candidate.get("operation") or "")
                for candidate in candidate_work
            ]
            secondary_matches = [
                expected
                for expected in secondary_expected
                if _candidate_operation_matches(candidate_operations, expected)
            ]
            candidate_metrics = _candidate_work_metrics(
                turn_spec=turn_spec,
                candidate_work=candidate_work,
                selected_operation=operation,
                previous_candidate_operations=previous_candidate_operations,
            )
            ranking_audit = _ranking_audit(
                turn_spec=turn_spec,
                mapped_work=mapped_work,
                candidate_metrics=candidate_metrics,
            )
            turn_results.append(
                {
                    "contract": "operational_real_world_turn_result.v1",
                    "turn": turn_index,
                    "user": turn_spec.get("user"),
                    "response": getattr(state, "response", None),
                    "expected": {
                        "operation": turn_spec.get("expected_operation"),
                        "category": turn_spec.get("expected_category"),
                        "outcome": turn_spec.get("expected_outcome"),
                        "transition": expected_transition,
                        "secondary_operations": secondary_expected,
                    },
                    "mapped_work": mapped_work,
                    "comparison": comparison,
                    "transition": {
                        "expected": expected_transition,
                        "actual": actual_transition,
                        "match": transition_match,
                        "previous_operation": previous_operation,
                        "current_operation": operation,
                    },
                    "multi_work": {
                        "expected_secondary_operations": secondary_expected,
                        "candidate_operations": candidate_operations,
                        "matched_secondary_operations": secondary_matches,
                        "detected": bool(secondary_expected) and bool(secondary_matches),
                    },
                    "candidate_work_metrics": candidate_metrics,
                    "ranking_audit": ranking_audit,
                    "runtime": {
                        "selected_program": getattr(state, "selected_program", None),
                        "runtime_execution_engine": _mapping((getattr(state, "facts", {}) or {}).get("runtime_execution_engine")),
                    },
                }
            )
            previous_operation = operation
            previous_operations.append(operation)
            previous_candidate_operations = candidate_operations
        metrics = _real_world_conversation_metrics(turn_results)
        results.append(
            {
                "contract": "operational_real_world_conversation_result.v1",
                "id": conversation.get("id"),
                "title": conversation.get("title"),
                "source": conversation.get("source"),
                "tags": list(conversation.get("tags") or []),
                "turn_count": len(turn_results),
                "metrics": metrics,
                "turns": turn_results,
            }
        )

    aggregate = _aggregate_operational_real_world_results(results)
    return {
        "contract": "operational_real_world_benchmark_result.v1",
        "benchmark": suite["benchmark"],
        "description": suite["description"],
        "domain": suite["domain"],
        "source_path": suite["path"],
        "conversation_count": len(results),
        "turn_count": sum(result["turn_count"] for result in results),
        "coverage": {
            "sources": suite["sources"],
            "conversation_count": len(results),
            "turn_count": sum(result["turn_count"] for result in results),
            "plugin_manifest_count": len(plugin_manifests),
        },
        "quality": aggregate["quality"],
        "errors": aggregate["errors"],
        "architecture": aggregate["architecture"],
        "conversations": results,
    }


def render_operational_real_world_benchmark_report(result: Mapping[str, Any]) -> str:
    quality = dict(result.get("quality") or {})
    errors = dict(result.get("errors") or {})
    architecture = dict(result.get("architecture") or {})
    lines = [
        "# ACA Operational Real-World Benchmark",
        "",
        f"- Benchmark: `{result.get('benchmark')}`",
        f"- Conversations: {result.get('conversation_count', 0)}",
        f"- Turns: {result.get('turn_count', 0)}",
        f"- Correct operation selection: {quality.get('correct_operation_selection_percentage', 0)}%",
        f"- Work transition accuracy: {quality.get('work_transition_accuracy_percentage', 0)}%",
        f"- Multi-work detection: {quality.get('multi_work_detection_percentage', 0)}%",
        f"- Candidate work recall: {quality.get('candidate_work_recall_percentage', 0)}%",
        f"- Candidate work precision: {quality.get('candidate_work_precision_percentage', 0)}%",
        f"- Work ranking accuracy: {quality.get('work_ranking_accuracy_percentage', 0)}%",
        f"- Ranking ambiguity rate: {quality.get('ranking_ambiguity_rate_percentage', 0)}%",
        f"- Missing state evidence: {quality.get('missing_state_evidence_count', 0)}",
        f"- Case state dependency rate: {quality.get('case_state_dependency_rate_percentage', 0)}%",
        f"- Case state projection available: {quality.get('case_state_projection_available_percentage', 0)}%",
        f"- Case state projection reconstructable: {quality.get('case_state_projection_reconstructable_percentage', 0)}%",
        f"- Case-state projected ranking accuracy: {quality.get('case_state_projected_ranking_accuracy_percentage', 0)}%",
        f"- Case-state projected ranking ambiguity: {quality.get('case_state_projected_ranking_ambiguity_rate_percentage', 0)}%",
        f"- Case-state projection resolved ambiguities: {quality.get('case_state_projection_resolved_ambiguity_count', 0)}",
        f"- Unresolved projected ranking errors: {quality.get('unresolved_projected_ranking_error_count', 0)}",
        f"- Ranking explanation coverage: {quality.get('ranking_explanation_coverage_percentage', 0)}%",
        f"- Work persistence errors: {quality.get('work_persistence_error_count', 0)}",
        f"- Operational drift: {quality.get('operational_drift_percentage', 0)}%",
        "",
        "## Stability",
        "",
        f"- Operational stability across turns: {quality.get('operational_stability_across_turns_percentage', 0)}%",
        f"- Candidate stability: {quality.get('candidate_stability_percentage', 0)}%",
        f"- Priority consistency: {quality.get('priority_consistency_percentage', 0)}%",
        f"- Work abandonment accuracy: {quality.get('work_abandonment_accuracy_percentage', 0)}%",
        f"- Secondary work detection: {quality.get('secondary_work_detection_percentage', 0)}%",
        f"- Suspended work accuracy: {quality.get('suspended_work_accuracy_percentage', 0)}%",
        f"- Recovered work accuracy: {quality.get('recovered_work_accuracy_percentage', 0)}%",
        f"- Mixed intent handling: {quality.get('mixed_intent_handling_percentage', 0)}%",
        "",
        "## Architecture",
        "",
        f"- Mapper mode: {architecture.get('mapper_mode')}",
        f"- Runtime mutations: {architecture.get('runtime_mutations')}",
        f"- Response changes: {architecture.get('response_changes')}",
        f"- Recommendation: {architecture.get('recommendation')}",
        "",
        "## Errors",
        "",
    ]
    counts = errors.get("counts") or {}
    if counts:
        for name, count in sorted(counts.items()):
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none detected by real-world operational rules")
    lines.extend(["", "## Conversation Summary", ""])
    for conversation in result.get("conversations") or []:
        metrics = dict(conversation.get("metrics") or {})
        lines.append(
            f"- `{conversation.get('id')}`: operation={metrics.get('operation_match_percentage')}%, "
            f"transition={metrics.get('transition_match_percentage')}%, "
            f"multi={metrics.get('multi_work_detection_percentage')}%, "
            f"errors={len(metrics.get('errors') or [])}"
        )
    lines.append("")
    return "\n".join(lines)


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
        f"- Template responses: {quality.get('template_response_count', 0)}",
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
        "reformulated_questions": _count_reformulated_questions(
            response_plan=response_plan,
            info_plan=info_plan,
            response_questions=response_questions,
        ),
        "answered_before_asking": 1 if _answered_before_asking(response, response_questions) else 0,
        "resumed_topic_success": 1 if _resumed_topic_success(response, recovery_actions, projections) else 0,
        "template_response_count": 1 if _has_template_response(response) else 0,
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
            "template_response_count",
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
        "template_response_count": metrics["template_response_count"],
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
    response_text = "\n".join(str(turn.get("response") or "") for turn in turn_results)
    last_response = str((turn_results[-1] if turn_results else {}).get("response") or "")
    for phrase in scenario.expectations.get("must_include_response") or []:
        if normalize_text(phrase) not in normalize_text(response_text):
            errors.append(
                {
                    "type": "expected_response_phrase_missing",
                    "severity": "medium",
                    "evidence": {"phrase": phrase, "scope": "scenario"},
                }
            )
    for phrase in scenario.expectations.get("must_not_include_response") or []:
        if normalize_text(phrase) in normalize_text(response_text):
            errors.append(
                {
                    "type": "forbidden_response_phrase",
                    "severity": "high",
                    "evidence": {"phrase": phrase, "scope": "scenario"},
                }
            )
    for phrase in scenario.expectations.get("must_include_last_response") or []:
        if normalize_text(phrase) not in normalize_text(last_response):
            errors.append(
                {
                    "type": "expected_response_phrase_missing",
                    "severity": "medium",
                    "evidence": {"phrase": phrase, "scope": "last_response"},
                }
            )
    for phrase in scenario.expectations.get("must_not_include_last_response") or []:
        if normalize_text(phrase) in normalize_text(last_response):
            errors.append(
                {
                    "type": "forbidden_response_phrase",
                    "severity": "high",
                    "evidence": {"phrase": phrase, "scope": "last_response"},
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
            "template_response_count",
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
            "template_response_count": metrics["template_response_count"],
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


def _aggregate_operational_governance_results(results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    metrics = Counter()
    errors = []
    for result in results:
        assessment = _mapping(result.get("assessment"))
        comparison = _mapping(result.get("comparison"))
        checks = _mapping(comparison.get("checks"))
        expected = _mapping(comparison.get("expected"))
        actual = _mapping(comparison.get("actual"))
        tool = _mapping(assessment.get("tool_availability"))
        metrics["scenario_count"] += 1
        if comparison.get("passed"):
            metrics["governance_passed"] += 1
        for name, passed in checks.items():
            if passed:
                metrics[f"{name}_passed"] += 1
            metrics[f"{name}_scored"] += 1
        if not bool(expected.get("execution_allowed")) and bool(assessment.get("execution_blocked")):
            metrics["unsafe_execution_detected"] += 1
        if not bool(expected.get("execution_allowed")):
            metrics["unsafe_execution_scored"] += 1
        if "missing_evidence" in set(expected.get("missing_preconditions_contains") or []):
            metrics["missing_evidence_scored"] += 1
            missing_types = set(actual.get("missing_precondition_types") or [])
            if "missing_evidence" in missing_types:
                metrics["missing_evidence_detected"] += 1
        if assessment.get("execution_allowed") and not assessment.get("requires_confirmation") and not assessment.get("requires_human_approval"):
            metrics["automatic_execution"] += 1
        if assessment.get("requires_confirmation"):
            metrics["requires_confirmation"] += 1
        if assessment.get("requires_human_approval"):
            metrics["requires_human_approval"] += 1
        if assessment.get("manual_only"):
            metrics["manual_only"] += 1
        if tool.get("required_tool"):
            metrics["tool_contract_dependent"] += 1
        if not expected.get("execution_allowed") and assessment.get("execution_allowed"):
            metrics["governance_false_positive"] += 1
            errors.append(
                {
                    "type": "governance_false_positive",
                    "scenario": result.get("id"),
                    "operation": _mapping(assessment.get("selected_work")).get("operation"),
                }
            )
        if expected.get("execution_allowed") and not assessment.get("execution_allowed"):
            metrics["governance_false_negative"] += 1
            errors.append(
                {
                    "type": "governance_false_negative",
                    "scenario": result.get("id"),
                    "operation": _mapping(assessment.get("selected_work")).get("operation"),
                }
            )
        if not comparison.get("passed"):
            errors.append(
                {
                    "type": "governance_comparison_failed",
                    "scenario": result.get("id"),
                    "checks": checks,
                    "actual": actual,
                    "expected": expected,
                }
            )
    total = metrics["scenario_count"] or 1
    error_counts = Counter(str(error.get("type")) for error in errors)
    return {
        "quality": {
            "governance_accuracy_percentage": _percent(metrics["governance_passed"], total),
            "unsafe_execution_detection_percentage": _percent(metrics["unsafe_execution_detected"], metrics["unsafe_execution_scored"]),
            "missing_evidence_detection_percentage": _percent(metrics["missing_evidence_detected"], metrics["missing_evidence_scored"]),
            "confirmation_requirement_accuracy_percentage": _percent(metrics["confirmation_match_passed"], metrics["confirmation_match_scored"]),
            "human_approval_accuracy_percentage": _percent(metrics["human_approval_match_passed"], metrics["human_approval_match_scored"]),
            "tool_availability_accuracy_percentage": _percent(metrics["tool_availability_match_passed"], metrics["tool_availability_match_scored"]),
            "idempotency_detection_percentage": _percent(metrics["idempotency_match_passed"], metrics["idempotency_match_scored"]),
            "governance_false_positive_count": metrics["governance_false_positive"],
            "governance_false_negative_count": metrics["governance_false_negative"],
        },
        "readiness": {
            "automatic_execution_count": metrics["automatic_execution"],
            "requires_confirmation_count": metrics["requires_confirmation"],
            "requires_human_approval_count": metrics["requires_human_approval"],
            "manual_only_count": metrics["manual_only"],
            "tool_contract_dependent_count": metrics["tool_contract_dependent"],
            "immediate_enablement_percentage": _percent(metrics["automatic_execution"], total),
            "recommendation": _operational_governance_recommendation(metrics, total),
        },
        "errors": {
            "count": len(errors),
            "counts": dict(sorted(error_counts.items())),
            "items": errors,
        },
    }


def _aggregate_operational_audit_ledger_results(results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    metrics = Counter()
    errors = []
    for result in results:
        comparison = _mapping(result.get("comparison"))
        checks = _mapping(comparison.get("checks"))
        ledger = _mapping(result.get("ledger_record"))
        completeness = _mapping(ledger.get("completeness"))
        metrics["scenario_count"] += 1
        if comparison.get("passed"):
            metrics["ledger_passed"] += 1
        for name, passed in checks.items():
            if passed:
                metrics[f"{name}_passed"] += 1
            metrics[f"{name}_scored"] += 1
        if completeness.get("complete"):
            metrics["reconstructable_operation"] += 1
        if not ledger.get("persistent"):
            metrics["requires_durable_persistence"] += 1
        if not comparison.get("passed"):
            errors.append(
                {
                    "type": "ledger_comparison_failed",
                    "scenario": result.get("id"),
                    "checks": checks,
                    "actual": comparison.get("actual"),
                    "expected": comparison.get("expected"),
                }
            )
    total = metrics["scenario_count"] or 1
    error_counts = Counter(str(error.get("type")) for error in errors)
    return {
        "quality": {
            "ledger_completeness_percentage": _percent(metrics["ledger_completeness_match_passed"], metrics["ledger_completeness_match_scored"]),
            "audit_trace_completeness_percentage": _percent(metrics["audit_trace_complete_match_passed"], metrics["audit_trace_complete_match_scored"]),
            "idempotency_coverage_percentage": _percent(metrics["idempotency_coverage_match_passed"], metrics["idempotency_coverage_match_scored"]),
            "receipt_coverage_percentage": _percent(metrics["receipt_coverage_match_passed"], metrics["receipt_coverage_match_scored"]),
            "compensation_coverage_percentage": _percent(metrics["compensation_coverage_match_passed"], metrics["compensation_coverage_match_scored"]),
            "replay_safety_percentage": _percent(metrics["replay_safety_match_passed"], metrics["replay_safety_match_scored"]),
            "duplicate_detection_accuracy_percentage": _percent(metrics["duplicate_detection_match_passed"], metrics["duplicate_detection_match_scored"]),
            "execution_status_accuracy_percentage": _percent(metrics["execution_status_match_passed"], metrics["execution_status_match_scored"]),
            "ledger_accuracy_percentage": _percent(metrics["ledger_passed"], total),
        },
        "readiness": {
            "reconstructable_operation_count": metrics["reconstructable_operation"],
            "requires_durable_persistence_count": metrics["requires_durable_persistence"],
            "conceptual_completeness_percentage": _percent(metrics["reconstructable_operation"], total),
            "recommendation": _operational_audit_ledger_recommendation(metrics, total),
        },
        "errors": {
            "count": len(errors),
            "counts": dict(sorted(error_counts.items())),
            "items": errors,
        },
    }


def _register_operational_dry_run_tools(runtime: Any) -> None:
    engine = getattr(runtime, "tool_engine", None)
    if engine is None:
        return
    if not engine.can_execute(HandoffPackageDryRunAdapter.name):
        engine.register(HandoffPackageDryRunAdapter())


def _operational_dry_run_tool_request(
    *,
    scenario: Mapping[str, Any],
    conversation_id: str,
    mapped_work: Mapping[str, Any],
    governance_assessment: Mapping[str, Any],
    ledger_record: Mapping[str, Any],
) -> ToolRequest:
    tool_name = str(scenario.get("expected_tool") or "handoff_package")
    return ToolRequest(
        tool_name=tool_name,
        intent="prepare_handoff_package",
        payload={
            "conversation_id": conversation_id,
            "mapped_work": dict(mapped_work),
            "selected_work": dict(_mapping(mapped_work.get("selected_work"))),
            "candidate_work": list(mapped_work.get("candidate_work") or []),
            "case_state_projection": dict(_mapping(mapped_work.get("case_state_projection"))),
            "governance_assessment": dict(governance_assessment),
            "ledger_record": dict(ledger_record),
        },
    )


def _compare_operational_dry_run(
    *,
    scenario: Mapping[str, Any],
    mapped_work: Mapping[str, Any],
    governance_assessment: Mapping[str, Any],
    ledger_record: Mapping[str, Any],
    dry_run_result: Any,
    replay_result: Any,
) -> Dict[str, Any]:
    selected = _mapping(mapped_work.get("selected_work"))
    expected_operation = str(scenario.get("expected_operation") or "prepare_handoff")
    expected_tool = str(scenario.get("expected_tool") or "handoff_package")
    expected_receipt_status = str(scenario.get("expected_receipt_status") or "dry_run_completed")
    dry_execution = _mapping(getattr(dry_run_result, "execution", {}))
    replay_execution = _mapping(getattr(replay_result, "execution", {}))
    dry_evidence = _mapping(getattr(dry_run_result, "evidence", {}))
    replay_evidence = _mapping(getattr(replay_result, "evidence", {}))
    receipt = _mapping(dry_evidence.get("projected_receipt"))
    replay_receipt = _mapping(replay_evidence.get("projected_receipt"))
    ledger_completeness = _mapping(ledger_record.get("completeness"))
    idempotency = _mapping(ledger_record.get("idempotency"))
    checks = {
        "operation_match": str(selected.get("operation") or "") == expected_operation,
        "tool_match": dry_run_result.tool_name == expected_tool,
        "governance_allowed": bool(governance_assessment.get("execution_allowed")),
        "ledger_complete": bool(ledger_completeness.get("complete")),
        "receipt_generated": bool(receipt.get("receipt_id")) and str(receipt.get("status") or "") == expected_receipt_status,
        "dry_run_action": dry_execution.get("action") == "dry_run" and not bool(dry_execution.get("executed")),
        "side_effect_free": not bool(receipt.get("side_effects")) and not bool(receipt.get("external_write")),
        "replay_consistent": replay_result.success
        and replay_execution.get("action") == "replay"
        and replay_receipt.get("receipt_id") == receipt.get("receipt_id"),
        "idempotency_covered": bool(idempotency.get("covered")) or bool(receipt.get("idempotency_key")),
    }
    score = sum(1 for value in checks.values() if value)
    return {
        "contract": "operational_dry_run_comparison.v1",
        "checks": checks,
        "score": score,
        "max_score": len(checks),
        "passed": score == len(checks),
        "actual": {
            "operation": selected.get("operation"),
            "tool": dry_run_result.tool_name,
            "governance_allowed": governance_assessment.get("execution_allowed"),
            "ledger_complete": ledger_completeness.get("complete"),
            "receipt_status": receipt.get("status"),
            "dry_run_action": dry_execution.get("action"),
            "executed": dry_execution.get("executed"),
            "replay_action": replay_execution.get("action"),
            "side_effects": receipt.get("side_effects"),
            "external_write": receipt.get("external_write"),
        },
        "expected": {
            "operation": expected_operation,
            "tool": expected_tool,
            "receipt_status": expected_receipt_status,
        },
    }


def _aggregate_operational_dry_run_results(results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    metrics = Counter()
    errors = []
    for result in results:
        comparison = _mapping(result.get("comparison"))
        checks = _mapping(comparison.get("checks"))
        metrics["scenario_count"] += 1
        if comparison.get("passed"):
            metrics["end_to_end_success"] += 1
        for name, passed in checks.items():
            if passed:
                metrics[f"{name}_passed"] += 1
            metrics[f"{name}_scored"] += 1
        if not comparison.get("passed"):
            failed = sorted(name for name, passed in checks.items() if not passed)
            errors.append(
                {
                    "type": "dry_run_comparison_failed",
                    "scenario": result.get("id"),
                    "failed_checks": failed,
                    "actual": comparison.get("actual"),
                    "expected": comparison.get("expected"),
                }
            )
    total = metrics["scenario_count"] or 1
    error_counts = Counter(str(error.get("type")) for error in errors)
    return {
        "quality": {
            "end_to_end_success_percentage": _percent(metrics["end_to_end_success"], total),
            "candidate_tool_coherence_percentage": _percent(metrics["operation_match_passed"] + metrics["tool_match_passed"], metrics["operation_match_scored"] + metrics["tool_match_scored"]),
            "governance_pass_percentage": _percent(metrics["governance_allowed_passed"], metrics["governance_allowed_scored"]),
            "ledger_completeness_percentage": _percent(metrics["ledger_complete_passed"], metrics["ledger_complete_scored"]),
            "receipt_generated_percentage": _percent(metrics["receipt_generated_passed"], metrics["receipt_generated_scored"]),
            "side_effect_free_percentage": _percent(metrics["side_effect_free_passed"], metrics["side_effect_free_scored"]),
            "replay_consistency_percentage": _percent(metrics["replay_consistent_passed"], metrics["replay_consistent_scored"]),
            "idempotency_coverage_percentage": _percent(metrics["idempotency_covered_passed"], metrics["idempotency_covered_scored"]),
            "dry_run_action_percentage": _percent(metrics["dry_run_action_passed"], metrics["dry_run_action_scored"]),
        },
        "architecture": {
            "runtime_mutations": False,
            "visible_response_changes": False,
            "tool_execution_mode": "dry_run",
            "tool": HandoffPackageDryRunAdapter.name,
            "uses_runtime_executor_outputs": True,
            "uses_candidate_work": True,
            "uses_case_state_projection": True,
            "uses_governance_gate": True,
            "uses_operational_audit_ledger": True,
            "uses_tool_contract": True,
        },
        "errors": {
            "count": len(errors),
            "counts": dict(sorted(error_counts.items())),
            "items": errors,
        },
    }


def _register_operational_production_tools(runtime: Any, *, package_store_path: str | Path) -> None:
    engine = getattr(runtime, "tool_engine", None)
    if engine is None:
        return
    engine.register(HandoffPackageAdapter(store_path=package_store_path))


def _operational_production_tool_request(
    *,
    scenario: Mapping[str, Any],
    attempt: Mapping[str, Any],
    conversation_id: str,
    idempotency_key: str,
    mapped_work: Mapping[str, Any],
    governance_assessment: Mapping[str, Any],
    ledger_record: Mapping[str, Any],
) -> ToolRequest:
    tool_name = str(scenario.get("expected_tool") or "handoff_package")
    return ToolRequest(
        tool_name=tool_name,
        intent="prepare_handoff_package",
        payload={
            "conversation_id": conversation_id,
            "idempotency_key": idempotency_key,
            "failure_mode": str(attempt.get("failure_mode") or ""),
            "mapped_work": dict(mapped_work),
            "selected_work": dict(_mapping(mapped_work.get("selected_work"))),
            "candidate_work": list(mapped_work.get("candidate_work") or []),
            "case_state_projection": dict(_mapping(mapped_work.get("case_state_projection"))),
            "governance_assessment": dict(governance_assessment),
            "ledger_record": dict(ledger_record),
        },
    )


def _blocked_tool_result(tool_name: str, *, reason: str) -> ToolResult:
    return ToolResult(
        tool_name=tool_name,
        success=False,
        error=reason,
        evidence={
            "external_receipt": {
                "status": "blocked_by_governance",
                "external_status": "blocked_before_execution",
                "receipt_id": "",
                "replayable": False,
            },
            "tool_request": {},
            "tool_response": {"status": "blocked_by_governance", "error": reason},
        },
        execution={
            "tool_name": tool_name,
            "action": "reject",
            "executed": False,
            "execution_contract": {},
        },
    )


def _compare_operational_production(
    *,
    scenario: Mapping[str, Any],
    attempts: Sequence[Mapping[str, Any]],
    replay_result: Any,
    package_store_path: Path,
    ledger_store: JsonlOperationalAuditLedgerStore,
) -> Dict[str, Any]:
    final_attempt = _mapping(attempts[-1] if attempts else {})
    ledger = _mapping(final_attempt.get("ledger_record"))
    execution_status = _mapping(ledger.get("execution_status"))
    receipt = _mapping(ledger.get("external_receipt"))
    tool_execution = _mapping(final_attempt.get("tool_execution"))
    expected_state = str(scenario.get("expected_execution_state") or "executed")
    expected_package_count = scenario.get("expected_package_records")
    package_records = _read_jsonl_records(package_store_path)
    replay_evidence = _mapping(getattr(replay_result, "evidence", {}) if replay_result is not None else {})
    replay_receipt = _mapping(replay_evidence.get("external_receipt") or replay_evidence.get("projected_receipt"))
    checks = {
        "operation_match": str(_mapping(ledger.get("selected_work")).get("operation") or "") == str(scenario.get("expected_operation") or "prepare_handoff"),
        "tool_match": str(_mapping(ledger.get("tool")).get("name") or "") == str(scenario.get("expected_tool") or "handoff_package"),
        "execution_state_match": str(execution_status.get("state") or "") == expected_state,
        "real_execution_recorded": bool(tool_execution.get("executed")) == bool(scenario.get("expected_tool_called", True)),
        "ledger_persisted": bool(ledger.get("persistent")),
        "ledger_complete": bool(_mapping(ledger.get("completeness")).get("complete")) == bool(scenario.get("expected_ledger_complete", True)),
        "receipt_status_match": str(receipt.get("status") or "") == str(scenario.get("expected_receipt_status") or receipt.get("status") or ""),
        "receipt_validity_match": bool(receipt.get("receipt_id")) == bool(scenario.get("expected_valid_receipt", True)),
        "idempotency_present": bool(_mapping(ledger.get("idempotency")).get("key")),
        "replay_consistent": not bool(scenario.get("expect_replay", True))
        or (
            replay_result is not None
            and bool(getattr(replay_result, "success", False))
            and replay_receipt.get("receipt_id") == receipt.get("receipt_id")
        ),
        "package_record_count_match": expected_package_count is None or len(package_records) == int(expected_package_count),
    }
    score = sum(1 for value in checks.values() if value)
    return {
        "contract": "operational_production_comparison.v1",
        "checks": checks,
        "score": score,
        "max_score": len(checks),
        "passed": score == len(checks),
        "actual": {
            "operation": _mapping(ledger.get("selected_work")).get("operation"),
            "tool": _mapping(ledger.get("tool")).get("name"),
            "execution_state": execution_status.get("state"),
            "receipt_status": receipt.get("status"),
            "receipt_id_present": bool(receipt.get("receipt_id")),
            "package_records": len(package_records),
            "ledger_records": len(ledger_store.records()),
        },
        "expected": {
            "operation": scenario.get("expected_operation") or "prepare_handoff",
            "tool": scenario.get("expected_tool") or "handoff_package",
            "execution_state": expected_state,
            "receipt_status": scenario.get("expected_receipt_status"),
            "valid_receipt": scenario.get("expected_valid_receipt", True),
            "package_records": expected_package_count,
        },
    }


def _aggregate_operational_production_results(results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    metrics = Counter()
    errors = []
    for result in results:
        comparison = _mapping(result.get("comparison"))
        checks = _mapping(comparison.get("checks"))
        metrics["scenario_count"] += 1
        if comparison.get("passed"):
            metrics["production_passed"] += 1
        for name, passed in checks.items():
            if passed:
                metrics[f"{name}_passed"] += 1
            metrics[f"{name}_scored"] += 1
        state = str(_mapping(_mapping((result.get("attempts") or [{}])[-1]).get("ledger_record")).get("execution_status", {}).get("state") or "")
        if state in {"tool_timeout", "tool_unavailable", "invalid_receipt"} and comparison.get("passed"):
            metrics["failure_handled"] += 1
        if state in {"tool_timeout", "tool_unavailable", "invalid_receipt"}:
            metrics["failure_scored"] += 1
        if not comparison.get("passed"):
            errors.append(
                {
                    "type": "production_comparison_failed",
                    "scenario": result.get("id"),
                    "failed_checks": sorted(name for name, passed in checks.items() if not passed),
                    "actual": comparison.get("actual"),
                    "expected": comparison.get("expected"),
                }
            )
    total = metrics["scenario_count"] or 1
    error_counts = Counter(str(error.get("type")) for error in errors)
    return {
        "quality": {
            "production_success_percentage": _percent(metrics["production_passed"], total),
            "real_execution_percentage": _percent(metrics["real_execution_recorded_passed"], metrics["real_execution_recorded_scored"]),
            "ledger_persistence_percentage": _percent(metrics["ledger_persisted_passed"], metrics["ledger_persisted_scored"]),
            "receipt_coverage_percentage": _percent(metrics["receipt_validity_match_passed"], metrics["receipt_validity_match_scored"]),
            "replay_consistency_percentage": _percent(metrics["replay_consistent_passed"], metrics["replay_consistent_scored"]),
            "idempotency_accuracy_percentage": _percent(metrics["idempotency_present_passed"], metrics["idempotency_present_scored"]),
            "failure_handling_percentage": _percent(metrics["failure_handled"], metrics["failure_scored"]),
            "ledger_consistency_percentage": _percent(metrics["ledger_complete_passed"], metrics["ledger_complete_scored"]),
        },
        "architecture": {
            "runtime_redesigned": False,
            "conversation_contracts_modified": False,
            "tool_execution_mode": "official",
            "durable_ledger": "jsonl",
            "tool": HandoffPackageAdapter.name,
            "uses_runtime_executor_outputs": True,
            "uses_candidate_work": True,
            "uses_case_state_projection": True,
            "uses_governance_gate": True,
            "uses_operational_audit_ledger": True,
            "uses_tool_contract": True,
        },
        "errors": {
            "count": len(errors),
            "counts": dict(sorted(error_counts.items())),
            "items": errors,
        },
    }


def _stable_benchmark_idempotency(conversation_id: str, scenario: Mapping[str, Any]) -> str:
    return f"prod-{_stable_text_id(conversation_id, str(scenario.get('id') or 'scenario'))}"


def _stable_text_id(*parts: str) -> str:
    import hashlib

    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def _tool_result_to_dict(result: Any) -> Dict[str, Any]:
    if result is None:
        return {}
    return {
        "tool_name": getattr(result, "tool_name", None),
        "success": getattr(result, "success", None),
        "evidence": dict(getattr(result, "evidence", {}) or {}),
        "error": getattr(result, "error", None),
        "execution": dict(getattr(result, "execution", {}) or {}),
    }


def _mapped_work_for_governance_scenario(
    *,
    scenario: Mapping[str, Any],
    runtime: Any,
    ordinal: int,
    plugin_manifests: Sequence[Mapping[str, Any]],
    tool_contracts: Mapping[str, Any],
) -> Dict[str, Any]:
    if scenario.get("work_fixture"):
        return _mapped_work_from_fixture(_mapping(scenario.get("work_fixture")))

    conversation_id = f"operational-governance:{ordinal}:{scenario.get('id')}"
    turns = list(scenario.get("turns") or [{"user": scenario.get("initial_message") or ""}])
    state = None
    for turn in turns:
        message = str(_mapping(turn).get("user") if isinstance(turn, Mapping) else turn)
        state = runtime.process(
            Event(
                type="user_message",
                payload=message,
                metadata={"conversation_id": conversation_id},
            )
        )
    if state is None:
        return _mapped_work_from_fixture({"operation": "no_operational_work_identified"})
    state_snapshot = state.to_dict()
    mapped = map_operational_work(
        state_snapshot,
        plugin_manifests=plugin_manifests,
        tool_contracts=tool_contracts,
    )
    mapped["source_snapshot"] = state_snapshot
    return mapped


def _mapped_work_from_fixture(fixture: Mapping[str, Any]) -> Dict[str, Any]:
    operation = str(fixture.get("operation") or "no_operational_work_identified")
    category = str(fixture.get("category") or "preparatory")
    expected_outcome = str(fixture.get("expected_outcome") or "prepared")
    candidate = {
        "operation": operation,
        "category": category,
        "expected_outcome": expected_outcome,
        "priority": int(fixture.get("priority") or 100),
        "status": str(fixture.get("status") or "pending"),
        "work_role": str(fixture.get("work_role") or "primary"),
        "evidence": dict(_mapping(fixture.get("evidence")) or {"source": "governance_benchmark_fixture"}),
        "confidence": float(fixture.get("confidence") or 0.95),
        "dependency": dict(_mapping(fixture.get("dependency"))),
        "selection_reason": str(fixture.get("selection_reason") or "selected_work_supplied_by_governance_benchmark"),
        "blocked": bool(fixture.get("blocked", False)),
        "blocked_by": list(fixture.get("blocked_by") or []),
        "rank": 1,
    }
    return {
        "contract": "operational_work_shadow.v1",
        "component": "operational_work_mapper",
        "mode": "shadow",
        "passive": True,
        "mutates_state": False,
        "changes_response": False,
        "candidate_work": [candidate],
        "case_state_projection": _mapping(fixture.get("case_state_projection")),
        "selected_work": {
            "operation": operation,
            "category": category,
            "expected_outcome": expected_outcome,
            "confidence": candidate["confidence"],
            "rank": 1,
            "priority": candidate["priority"],
            "status": candidate["status"],
        },
        "expected_outcome": expected_outcome,
        "operational_category": category,
        "required_information": list(fixture.get("required_information") or []),
        "available_tools": list(fixture.get("available_tools") or []),
        "blocked_by": list(fixture.get("blocked_by") or []),
        "impossible_work_suggested": False,
        "operational_value": int(fixture.get("operational_value") or 1),
        "confidence": candidate["confidence"],
        "evidence": dict(_mapping(fixture.get("evidence"))),
    }


def _operational_governance_recommendation(metrics: Counter, total: int) -> str:
    if metrics["governance_false_positive"]:
        return "No: governance allowed at least one operation that should have been blocked."
    high_risk = metrics["requires_human_approval"] + metrics["manual_only"]
    immediate = _percent(metrics["automatic_execution"], total)
    if immediate >= 25 and high_risk:
        return "Parcialmente: low-risk work can be enabled after audit, but high-risk operations remain gated."
    if immediate > 0:
        return "Parcialmente: only low-risk preparation is immediately eligible."
    return "No: keep all operational execution in shadow until governance preconditions are met."


def _operational_audit_ledger_recommendation(metrics: Counter, total: int) -> str:
    if metrics["ledger_passed"] == total and metrics["reconstructable_operation"] == total:
        return "Si: the ledger projection is conceptually complete; production still needs durable persistence."
    if metrics["ledger_passed"] >= max(total - 1, 0):
        return "Parcialmente: ledger projection is close, but remaining audit gaps must be closed before production."
    return "No: audit reconstruction is not reliable enough for operational execution."


def _aggregate_operational_results(results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    metrics = Counter()
    outcome_counts = Counter()
    operation_counts = Counter()
    category_counts = Counter()
    observed_components = Counter()
    errors = []
    equivalence_groups: dict[str, list[str]] = {}

    for result in results:
        mapped_work = _mapping(result.get("mapped_work"))
        selected = _mapping(mapped_work.get("selected_work"))
        comparison = _mapping(result.get("comparison"))
        operation = str(selected.get("operation") or "")
        category = str(selected.get("category") or mapped_work.get("operational_category") or "")
        outcome = str(selected.get("expected_outcome") or mapped_work.get("expected_outcome") or "")
        operation_counts[operation] += 1
        category_counts[category] += 1
        outcome_counts[outcome] += 1

        if operation and operation != "no_operational_work_identified":
            metrics["work_identified"] += 1
        if int(mapped_work.get("operational_value") or 0) > 0:
            metrics["useful_work_turns"] += 1
        metrics["operational_value_total"] += int(mapped_work.get("operational_value") or 0)
        if comparison.get("operation_match"):
            metrics["operation_match"] += 1
        if comparison.get("category_match"):
            metrics["category_match"] += 1
        if comparison.get("outcome_match"):
            metrics["outcome_match"] += 1
        if comparison.get("impossible_work_suggested"):
            metrics["impossible_work"] += 1
        if _is_false_positive(result):
            metrics["false_positive"] += 1
        if _is_conversation_work_confusion(result):
            metrics["conversation_work_confusion"] += 1
        if _mapping(_mapping(mapped_work.get("coherence")).get("conversation_plan")).get("coherent"):
            metrics["conversation_plan_coherent"] += 1
        if _mapping(_mapping(mapped_work.get("coherence")).get("execution_plan")).get("coherent"):
            metrics["execution_plan_coherent"] += 1
        if _mapping(_mapping(mapped_work.get("coherence")).get("policy")).get("coherent"):
            metrics["policy_coherent"] += 1
        for component, used in _mapping(mapped_work.get("observed_inputs")).items():
            if used:
                observed_components[str(component)] += 1
        group = result.get("equivalence_group")
        if group:
            equivalence_groups.setdefault(str(group), []).append(operation)
        if not comparison.get("operation_match"):
            errors.append(
                {
                    "type": "operation_mismatch",
                    "severity": "medium",
                    "scenario": result.get("id"),
                    "expected": comparison.get("expected_operation"),
                    "actual": comparison.get("actual_operation"),
                }
            )
        if comparison.get("impossible_work_suggested"):
            errors.append(
                {
                    "type": "impossible_work_suggested",
                    "severity": "high",
                    "scenario": result.get("id"),
                    "operation": operation,
                }
            )

    total = len(results) or 1
    stable_groups = sum(
        1
        for operations in equivalence_groups.values()
        if len(set(operations)) <= 1
    )
    scored_groups = len(equivalence_groups)
    return {
        "quality": {
            "work_identified_count": metrics["work_identified"],
            "work_identified_percentage": _percent(metrics["work_identified"], total),
            "correct_operation_selection_count": metrics["operation_match"],
            "correct_operation_selection_percentage": _percent(metrics["operation_match"], total),
            "category_match_percentage": _percent(metrics["category_match"], total),
            "outcome_match_percentage": _percent(metrics["outcome_match"], total),
            "useful_work_turns": metrics["useful_work_turns"],
            "useful_work_percentage": _percent(metrics["useful_work_turns"], total),
            "operational_value_total": metrics["operational_value_total"],
            "operational_value_per_turn": round(metrics["operational_value_total"] / total, 2),
            "false_positive_count": metrics["false_positive"],
            "false_positive_percentage": _percent(metrics["false_positive"], total),
            "impossible_work_count": metrics["impossible_work"],
            "impossible_work_percentage": _percent(metrics["impossible_work"], total),
            "conversation_work_confusion_count": metrics["conversation_work_confusion"],
            "conversation_work_confusion_percentage": _percent(metrics["conversation_work_confusion"], total),
            "conversation_plan_coherence_percentage": _percent(metrics["conversation_plan_coherent"], total),
            "execution_plan_coherence_percentage": _percent(metrics["execution_plan_coherent"], total),
            "policy_coherence_percentage": _percent(metrics["policy_coherent"], total),
            "equivalent_group_count": scored_groups,
            "equivalent_group_stability_percentage": _percent(stable_groups, scored_groups),
            "operations": dict(sorted(operation_counts.items())),
            "categories": dict(sorted(category_counts.items())),
            "outcomes": dict(sorted(outcome_counts.items())),
        },
        "architecture": {
            "mapper_mode": "shadow",
            "runtime_mutations": 0,
            "response_changes": 0,
            "observed_components": sorted(observed_components),
            "observed_component_use_counts": dict(sorted(observed_components.items())),
            "value_signal": _operational_architecture_takeaway(metrics, total),
        },
        "errors": {
            "count": len(errors),
            "counts": dict(sorted(Counter(error["type"] for error in errors).items())),
            "examples": errors[:20],
        },
    }


def _real_world_conversation_metrics(turn_results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    metrics = Counter()
    errors = []
    for turn in turn_results:
        comparison = _mapping(turn.get("comparison"))
        transition = _mapping(turn.get("transition"))
        multi_work = _mapping(turn.get("multi_work"))
        candidate_metrics = _mapping(turn.get("candidate_work_metrics"))
        ranking_audit = _mapping(turn.get("ranking_audit"))
        if comparison.get("operation_match"):
            metrics["operation_match"] += 1
        if comparison.get("category_match"):
            metrics["category_match"] += 1
        if comparison.get("outcome_match"):
            metrics["outcome_match"] += 1
        if transition.get("expected"):
            metrics["transition_scored"] += 1
            if transition.get("match"):
                metrics["transition_match"] += 1
        if transition.get("expected") == "persist":
            metrics["stability_scored"] += 1
            if transition.get("actual") == "persist":
                metrics["stable_turns"] += 1
        if transition.get("expected") == "abandon":
            metrics["abandonment_scored"] += 1
            if transition.get("match"):
                metrics["abandonment_match"] += 1
        if multi_work.get("expected_secondary_operations"):
            metrics["multi_work_scored"] += 1
            if multi_work.get("detected"):
                metrics["multi_work_detected"] += 1
        metrics["candidate_recall_numerator"] += int(candidate_metrics.get("candidate_recall_numerator") or 0)
        metrics["candidate_recall_denominator"] += int(candidate_metrics.get("candidate_recall_denominator") or 0)
        metrics["candidate_precision_numerator"] += int(candidate_metrics.get("candidate_precision_numerator") or 0)
        metrics["candidate_precision_denominator"] += int(candidate_metrics.get("candidate_precision_denominator") or 0)
        if candidate_metrics.get("ranking_scored"):
            metrics["ranking_scored"] += 1
            if candidate_metrics.get("ranking_match"):
                metrics["ranking_match"] += 1
        if candidate_metrics.get("secondary_scored"):
            metrics["secondary_scored"] += 1
            if candidate_metrics.get("secondary_match"):
                metrics["secondary_match"] += 1
        if candidate_metrics.get("suspended_scored"):
            metrics["suspended_scored"] += 1
            if candidate_metrics.get("suspended_match"):
                metrics["suspended_match"] += 1
        if candidate_metrics.get("recovered_scored"):
            metrics["recovered_scored"] += 1
            if candidate_metrics.get("recovered_match"):
                metrics["recovered_match"] += 1
        if candidate_metrics.get("candidate_stability_scored"):
            metrics["candidate_stability_scored"] += 1
            if candidate_metrics.get("candidate_stable"):
                metrics["candidate_stable"] += 1
        if candidate_metrics.get("priority_consistency_scored"):
            metrics["priority_consistency_scored"] += 1
            if candidate_metrics.get("priority_consistent"):
                metrics["priority_consistent"] += 1
        if ranking_audit.get("ranking_scored"):
            metrics["ranking_audit_scored"] += 1
            if ranking_audit.get("ranking_ambiguous"):
                metrics["ranking_ambiguous"] += 1
            if ranking_audit.get("case_state_projection_available"):
                metrics["case_state_projection_available"] += 1
            if ranking_audit.get("case_state_projection_reconstructable"):
                metrics["case_state_projection_reconstructable"] += 1
            if ranking_audit.get("case_state_projected_ranking_match"):
                metrics["case_state_projected_ranking_match"] += 1
            if ranking_audit.get("case_state_projected_ranking_ambiguous"):
                metrics["case_state_projected_ranking_ambiguous"] += 1
            if ranking_audit.get("case_state_projection_resolved_ambiguity"):
                metrics["case_state_projection_resolved_ambiguity"] += 1
            if ranking_audit.get("case_state_dependent"):
                metrics["case_state_dependent"] += 1
            if ranking_audit.get("missing_state_evidence"):
                metrics["missing_state_evidence"] += 1
            if ranking_audit.get("ranking_explanation_covered"):
                metrics["ranking_explanation_covered"] += 1
        if not comparison.get("operation_match"):
            metrics["operational_drift"] += 1
            errors.append(
                {
                    "type": "operational_drift",
                    "turn": turn.get("turn"),
                    "expected": comparison.get("expected_operation"),
                    "actual": comparison.get("actual_operation"),
                }
            )
        if _turn_has_persistence_error(turn):
            metrics["work_persistence_error"] += 1
            errors.append(
                {
                    "type": "work_persistence_error",
                    "turn": turn.get("turn"),
                    "transition": transition,
                }
            )
        if multi_work.get("expected_secondary_operations") and not multi_work.get("detected"):
            errors.append(
                {
                    "type": "multi_work_not_detected",
                    "turn": turn.get("turn"),
                    "expected_secondary": multi_work.get("expected_secondary_operations"),
                    "candidate_operations": multi_work.get("candidate_operations"),
                }
            )
        if candidate_metrics.get("ranking_scored") and not candidate_metrics.get("ranking_match"):
            resolved_by_projection = bool(ranking_audit.get("case_state_projection_resolved_ambiguity"))
            if not resolved_by_projection:
                metrics["unresolved_projected_ranking_error"] += 1
            errors.append(
                {
                    "type": "work_ranking_mismatch",
                    "turn": turn.get("turn"),
                    "expected": _mapping(turn.get("expected")).get("operation"),
                    "candidate_operations": candidate_metrics.get("candidate_operations"),
                    "resolved_by_case_state_projection": resolved_by_projection,
                }
            )
        if candidate_metrics.get("suspended_scored") and not candidate_metrics.get("suspended_match"):
            errors.append(
                {
                    "type": "suspended_work_not_detected",
                    "turn": turn.get("turn"),
                    "expected": candidate_metrics.get("expected_candidate_operations"),
                    "candidate_operations": candidate_metrics.get("candidate_operations"),
                }
            )
        if candidate_metrics.get("recovered_scored") and not candidate_metrics.get("recovered_match"):
            errors.append(
                {
                    "type": "recovered_work_not_detected",
                    "turn": turn.get("turn"),
                    "expected": candidate_metrics.get("expected_candidate_operations"),
                    "candidate_operations": candidate_metrics.get("candidate_operations"),
                }
            )
    total = len(turn_results) or 1
    return {
        "turn_count": len(turn_results),
        "operation_match_percentage": _percent(metrics["operation_match"], total),
        "category_match_percentage": _percent(metrics["category_match"], total),
        "outcome_match_percentage": _percent(metrics["outcome_match"], total),
        "transition_match_percentage": _percent(metrics["transition_match"], metrics["transition_scored"]),
        "multi_work_detection_percentage": _percent(metrics["multi_work_detected"], metrics["multi_work_scored"]),
        "candidate_work_recall_percentage": _percent(metrics["candidate_recall_numerator"], metrics["candidate_recall_denominator"]),
        "candidate_work_precision_percentage": _percent(metrics["candidate_precision_numerator"], metrics["candidate_precision_denominator"]),
        "work_ranking_accuracy_percentage": _percent(metrics["ranking_match"], metrics["ranking_scored"]),
        "secondary_work_detection_percentage": _percent(metrics["secondary_match"], metrics["secondary_scored"]),
        "suspended_work_accuracy_percentage": _percent(metrics["suspended_match"], metrics["suspended_scored"]),
        "recovered_work_accuracy_percentage": _percent(metrics["recovered_match"], metrics["recovered_scored"]),
        "candidate_stability_percentage": _percent(metrics["candidate_stable"], metrics["candidate_stability_scored"]),
        "priority_consistency_percentage": _percent(metrics["priority_consistent"], metrics["priority_consistency_scored"]),
        "ranking_ambiguity_rate_percentage": _percent(metrics["ranking_ambiguous"], metrics["ranking_audit_scored"]),
        "missing_state_evidence_count": metrics["missing_state_evidence"],
        "missing_state_evidence_percentage": _percent(metrics["missing_state_evidence"], metrics["ranking_audit_scored"]),
        "case_state_dependency_rate_percentage": _percent(metrics["case_state_dependent"], metrics["ranking_audit_scored"]),
        "case_state_projection_available_percentage": _percent(metrics["case_state_projection_available"], metrics["ranking_audit_scored"]),
        "case_state_projection_reconstructable_percentage": _percent(metrics["case_state_projection_reconstructable"], metrics["ranking_audit_scored"]),
        "case_state_projected_ranking_accuracy_percentage": _percent(metrics["case_state_projected_ranking_match"], metrics["ranking_audit_scored"]),
        "case_state_projected_ranking_ambiguity_rate_percentage": _percent(metrics["case_state_projected_ranking_ambiguous"], metrics["ranking_audit_scored"]),
        "case_state_projection_resolved_ambiguity_count": metrics["case_state_projection_resolved_ambiguity"],
        "unresolved_projected_ranking_error_count": metrics["unresolved_projected_ranking_error"],
        "ranking_explanation_coverage_percentage": _percent(metrics["ranking_explanation_covered"], metrics["ranking_audit_scored"]),
        "work_persistence_error_count": metrics["work_persistence_error"],
        "work_abandonment_accuracy_percentage": _percent(metrics["abandonment_match"], metrics["abandonment_scored"]),
        "operational_drift_count": metrics["operational_drift"],
        "operational_stability_across_turns_percentage": _percent(metrics["stable_turns"], metrics["stability_scored"]),
        "scored_transitions": metrics["transition_scored"],
        "scored_multi_work_turns": metrics["multi_work_scored"],
        "scored_candidate_operations": metrics["candidate_recall_denominator"],
        "scored_secondary_work_turns": metrics["secondary_scored"],
        "errors": errors,
    }


def _aggregate_operational_real_world_results(results: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    metrics = Counter()
    errors = []
    operation_counts = Counter()
    transition_counts = Counter()
    for conversation in results:
        conv_metrics = _mapping(conversation.get("metrics"))
        for key in (
            "turn_count",
            "work_persistence_error_count",
            "operational_drift_count",
            "scored_transitions",
            "scored_multi_work_turns",
        ):
            metrics[key] += int(conv_metrics.get(key) or 0)
        for turn in conversation.get("turns") or []:
            comparison = _mapping(turn.get("comparison"))
            transition = _mapping(turn.get("transition"))
            multi_work = _mapping(turn.get("multi_work"))
            candidate_metrics = _mapping(turn.get("candidate_work_metrics"))
            ranking_audit = _mapping(turn.get("ranking_audit"))
            selected = _mapping(_mapping(turn.get("mapped_work")).get("selected_work"))
            operation_counts[str(selected.get("operation") or "")] += 1
            transition_counts[str(transition.get("actual") or "")] += 1
            if comparison.get("operation_match"):
                metrics["operation_match"] += 1
            if comparison.get("category_match"):
                metrics["category_match"] += 1
            if comparison.get("outcome_match"):
                metrics["outcome_match"] += 1
            if transition.get("expected"):
                metrics["transition_scored"] += 1
                if transition.get("match"):
                    metrics["transition_match"] += 1
            if transition.get("expected") == "persist":
                metrics["stability_scored"] += 1
                if transition.get("actual") == "persist":
                    metrics["stable_turns"] += 1
            if transition.get("expected") == "abandon":
                metrics["abandonment_scored"] += 1
                if transition.get("match"):
                    metrics["abandonment_match"] += 1
            if multi_work.get("expected_secondary_operations"):
                metrics["multi_work_scored"] += 1
                if multi_work.get("detected"):
                    metrics["multi_work_detected"] += 1
            metrics["candidate_recall_numerator"] += int(candidate_metrics.get("candidate_recall_numerator") or 0)
            metrics["candidate_recall_denominator"] += int(candidate_metrics.get("candidate_recall_denominator") or 0)
            metrics["candidate_precision_numerator"] += int(candidate_metrics.get("candidate_precision_numerator") or 0)
            metrics["candidate_precision_denominator"] += int(candidate_metrics.get("candidate_precision_denominator") or 0)
            if candidate_metrics.get("ranking_scored"):
                metrics["ranking_scored"] += 1
                if candidate_metrics.get("ranking_match"):
                    metrics["ranking_match"] += 1
            if candidate_metrics.get("secondary_scored"):
                metrics["secondary_scored"] += 1
                if candidate_metrics.get("secondary_match"):
                    metrics["secondary_match"] += 1
            if candidate_metrics.get("suspended_scored"):
                metrics["suspended_scored"] += 1
                if candidate_metrics.get("suspended_match"):
                    metrics["suspended_match"] += 1
            if candidate_metrics.get("recovered_scored"):
                metrics["recovered_scored"] += 1
                if candidate_metrics.get("recovered_match"):
                    metrics["recovered_match"] += 1
            if candidate_metrics.get("candidate_stability_scored"):
                metrics["candidate_stability_scored"] += 1
                if candidate_metrics.get("candidate_stable"):
                    metrics["candidate_stable"] += 1
            if candidate_metrics.get("priority_consistency_scored"):
                metrics["priority_consistency_scored"] += 1
                if candidate_metrics.get("priority_consistent"):
                    metrics["priority_consistent"] += 1
            if ranking_audit.get("ranking_scored"):
                metrics["ranking_audit_scored"] += 1
                if ranking_audit.get("ranking_ambiguous"):
                    metrics["ranking_ambiguous"] += 1
                if ranking_audit.get("case_state_projection_available"):
                    metrics["case_state_projection_available"] += 1
                if ranking_audit.get("case_state_projection_reconstructable"):
                    metrics["case_state_projection_reconstructable"] += 1
                if ranking_audit.get("case_state_projected_ranking_match"):
                    metrics["case_state_projected_ranking_match"] += 1
                if ranking_audit.get("case_state_projected_ranking_ambiguous"):
                    metrics["case_state_projected_ranking_ambiguous"] += 1
                if ranking_audit.get("case_state_projection_resolved_ambiguity"):
                    metrics["case_state_projection_resolved_ambiguity"] += 1
                if ranking_audit.get("case_state_projected_ranking_ambiguous"):
                    metrics["unresolved_projected_ranking_error"] += 1
                if ranking_audit.get("case_state_dependent"):
                    metrics["case_state_dependent"] += 1
                if ranking_audit.get("missing_state_evidence"):
                    metrics["missing_state_evidence"] += 1
                if ranking_audit.get("ranking_explanation_covered"):
                    metrics["ranking_explanation_covered"] += 1
            if _is_mixed_intent_turn(turn):
                metrics["mixed_intent_scored"] += 1
                if comparison.get("operation_match") and (not multi_work.get("expected_secondary_operations") or multi_work.get("detected")):
                    metrics["mixed_intent_success"] += 1
        for error in conv_metrics.get("errors") or []:
            mapped = dict(error)
            mapped["conversation_id"] = conversation.get("id")
            errors.append(mapped)

    total_turns = metrics["turn_count"] or 1
    drift = metrics["operational_drift_count"]
    recommendation = _real_world_recommendation(metrics)
    return {
        "quality": {
            "correct_operation_selection_percentage": _percent(metrics["operation_match"], total_turns),
            "category_match_percentage": _percent(metrics["category_match"], total_turns),
            "outcome_match_percentage": _percent(metrics["outcome_match"], total_turns),
            "work_transition_accuracy_percentage": _percent(metrics["transition_match"], metrics["transition_scored"]),
            "multi_work_detection_percentage": _percent(metrics["multi_work_detected"], metrics["multi_work_scored"]),
            "candidate_work_recall_percentage": _percent(metrics["candidate_recall_numerator"], metrics["candidate_recall_denominator"]),
            "candidate_work_precision_percentage": _percent(metrics["candidate_precision_numerator"], metrics["candidate_precision_denominator"]),
            "work_ranking_accuracy_percentage": _percent(metrics["ranking_match"], metrics["ranking_scored"]),
            "secondary_work_detection_percentage": _percent(metrics["secondary_match"], metrics["secondary_scored"]),
            "suspended_work_accuracy_percentage": _percent(metrics["suspended_match"], metrics["suspended_scored"]),
            "recovered_work_accuracy_percentage": _percent(metrics["recovered_match"], metrics["recovered_scored"]),
            "candidate_stability_percentage": _percent(metrics["candidate_stable"], metrics["candidate_stability_scored"]),
            "priority_consistency_percentage": _percent(metrics["priority_consistent"], metrics["priority_consistency_scored"]),
            "ranking_ambiguity_rate_percentage": _percent(metrics["ranking_ambiguous"], metrics["ranking_audit_scored"]),
            "missing_state_evidence_count": metrics["missing_state_evidence"],
            "missing_state_evidence_percentage": _percent(metrics["missing_state_evidence"], metrics["ranking_audit_scored"]),
            "case_state_dependency_rate_percentage": _percent(metrics["case_state_dependent"], metrics["ranking_audit_scored"]),
            "case_state_projection_available_percentage": _percent(metrics["case_state_projection_available"], metrics["ranking_audit_scored"]),
            "case_state_projection_reconstructable_percentage": _percent(metrics["case_state_projection_reconstructable"], metrics["ranking_audit_scored"]),
            "case_state_projected_ranking_accuracy_percentage": _percent(metrics["case_state_projected_ranking_match"], metrics["ranking_audit_scored"]),
            "case_state_projected_ranking_ambiguity_rate_percentage": _percent(metrics["case_state_projected_ranking_ambiguous"], metrics["ranking_audit_scored"]),
            "case_state_projection_resolved_ambiguity_count": metrics["case_state_projection_resolved_ambiguity"],
            "unresolved_projected_ranking_error_count": metrics["unresolved_projected_ranking_error"],
            "ranking_explanation_coverage_percentage": _percent(metrics["ranking_explanation_covered"], metrics["ranking_audit_scored"]),
            "work_persistence_error_count": metrics["work_persistence_error_count"],
            "work_persistence_error_percentage": _percent(metrics["work_persistence_error_count"], total_turns),
            "work_abandonment_accuracy_percentage": _percent(metrics["abandonment_match"], metrics["abandonment_scored"]),
            "mixed_intent_handling_percentage": _percent(metrics["mixed_intent_success"], metrics["mixed_intent_scored"]),
            "operational_drift_count": drift,
            "operational_drift_percentage": _percent(drift, total_turns),
            "operational_stability_across_turns_percentage": _percent(metrics["stable_turns"], metrics["stability_scored"]),
            "scored_transition_count": metrics["transition_scored"],
            "scored_multi_work_turns": metrics["multi_work_scored"],
            "scored_candidate_operations": metrics["candidate_recall_denominator"],
            "scored_secondary_work_turns": metrics["secondary_scored"],
            "operations": dict(sorted(operation_counts.items())),
            "transitions": dict(sorted(transition_counts.items())),
        },
        "errors": {
            "count": len(errors),
            "counts": dict(sorted(Counter(error["type"] for error in errors).items())),
            "examples": errors[:30],
        },
        "architecture": {
            "mapper_mode": "shadow",
            "runtime_mutations": 0,
            "response_changes": 0,
            "recommendation": recommendation,
        },
    }


def _work_transition(
    *,
    operation: str,
    previous_operation: str,
    previous_operations: Sequence[str],
) -> str:
    if not previous_operation:
        return "start"
    if operation == previous_operation:
        return "persist"
    if operation in set(previous_operations[:-1]):
        return "resume"
    return "switch"


def _transition_matches(
    *,
    expected: str,
    actual: str,
    operation: str,
    previous_operation: str,
) -> bool:
    if not expected:
        return True
    if expected == actual:
        return True
    if expected == "repair":
        return operation == "repair_service_interaction"
    if expected == "abandon":
        return bool(previous_operation) and operation != previous_operation
    if expected == "complete":
        return operation in {"close_case_no_action", "prepare_case_summary"} or actual in {"switch", "persist"}
    return False


def _turn_has_persistence_error(turn: Mapping[str, Any]) -> bool:
    transition = _mapping(turn.get("transition"))
    expected = str(transition.get("expected") or "")
    actual = str(transition.get("actual") or "")
    if expected in {"switch", "resume", "abandon", "repair"} and actual == "persist":
        return True
    if expected == "persist" and actual not in {"persist"}:
        return True
    return False


def _candidate_work_metrics(
    *,
    turn_spec: Mapping[str, Any],
    candidate_work: Sequence[Mapping[str, Any]],
    selected_operation: str,
    previous_candidate_operations: Sequence[str],
) -> Dict[str, Any]:
    candidate_operations = [str(_mapping(candidate).get("operation") or "") for candidate in candidate_work]
    expected_primary = str(turn_spec.get("expected_operation") or "")
    expected_secondary = [str(item) for item in turn_spec.get("expected_secondary_operations") or []]
    expected_suspended = [str(item) for item in turn_spec.get("expected_suspended_operations") or []]
    expected_recovered = [str(item) for item in turn_spec.get("expected_recovered_operations") or []]
    expected_discarded = [str(item) for item in turn_spec.get("expected_discarded_operations") or []]
    expected_completed = [str(item) for item in turn_spec.get("expected_completed_operations") or []]
    expected_candidates = _unique_strings(
        [expected_primary]
        + expected_secondary
        + expected_suspended
        + expected_recovered
        + expected_discarded
        + expected_completed
    )
    matched_expected = [
        expected
        for expected in expected_candidates
        if _candidate_operation_matches(candidate_operations, expected)
    ]
    matched_candidates = [
        operation
        for operation in candidate_operations
        if _candidate_operation_matches(expected_candidates, operation)
    ]
    ranking_match = _candidate_operation_matches(candidate_operations[:1], expected_primary)
    secondary_match = _all_candidate_operations_match(candidate_operations, expected_secondary)
    suspended_match = _all_candidate_operations_with_status(
        candidate_work,
        expected_suspended,
        statuses={"suspended"},
        roles={"suspended"},
    )
    recovered_match = _all_candidate_operations_with_status(
        candidate_work,
        expected_recovered,
        statuses={"pending", "active"},
        roles={"recovered"},
    )
    completed_match = _all_candidate_operations_with_status(
        candidate_work,
        expected_completed,
        statuses={"completed"},
        roles={"completed"},
    )
    expected_transition = str(turn_spec.get("expected_transition") or "")
    stability_scored = bool(previous_candidate_operations) and expected_transition in {"persist", "resume"}
    stability_match = (
        _candidate_sets_stable(previous_candidate_operations, candidate_operations, selected_operation=selected_operation)
        if stability_scored
        else False
    )
    return {
        "expected_candidate_operations": expected_candidates,
        "candidate_operations": candidate_operations,
        "matched_expected_operations": matched_expected,
        "matched_candidate_operations": matched_candidates,
        "candidate_recall_numerator": len(matched_expected),
        "candidate_recall_denominator": len(expected_candidates),
        "candidate_precision_numerator": len(matched_candidates),
        "candidate_precision_denominator": len(candidate_operations),
        "ranking_scored": bool(expected_primary),
        "ranking_match": ranking_match,
        "secondary_scored": bool(expected_secondary),
        "secondary_match": secondary_match,
        "suspended_scored": bool(expected_suspended),
        "suspended_match": suspended_match,
        "recovered_scored": bool(expected_recovered),
        "recovered_match": recovered_match,
        "completed_scored": bool(expected_completed),
        "completed_match": completed_match,
        "candidate_stability_scored": stability_scored,
        "candidate_stable": stability_match,
        "priority_consistency_scored": len(candidate_work) > 1,
        "priority_consistent": _candidate_priority_consistent(candidate_work),
    }


def _ranking_audit(
    *,
    turn_spec: Mapping[str, Any],
    mapped_work: Mapping[str, Any],
    candidate_metrics: Mapping[str, Any],
) -> Dict[str, Any]:
    candidate_work = [
        _mapping(candidate)
        for candidate in mapped_work.get("candidate_work") or []
    ]
    expected_primary = str(turn_spec.get("expected_operation") or "")
    candidate_operations = [
        str(candidate.get("operation") or "")
        for candidate in candidate_work
    ]
    expected_present = _candidate_operation_matches(candidate_operations, expected_primary)
    ranking_match = bool(candidate_metrics.get("ranking_match"))
    ranking_scored = bool(candidate_metrics.get("ranking_scored"))
    ranking_ambiguous = bool(ranking_scored and expected_present and not ranking_match)
    projected_ranking = _mapping(mapped_work.get("case_state_projected_ranking"))
    projected_operations = [
        str(item.get("operation") or "")
        for item in projected_ranking.get("ranked_candidates") or []
        if isinstance(item, Mapping)
    ]
    projected_match = _candidate_operation_matches(projected_operations[:1], expected_primary)
    projected_ambiguous = bool(ranking_scored and expected_present and not projected_match)
    projection_resolved_ambiguity = bool(ranking_ambiguous and projected_match)
    projection = _mapping(mapped_work.get("case_state_projection"))
    projection_available = bool(projection)
    projection_reconstructable = bool(projection.get("reconstructable_each_turn"))
    case_state_dependent = bool(
        ranking_ambiguous
        and (
            _has_case_state_marker(str(turn_spec.get("user") or ""))
            or _has_candidate_state_conflict(candidate_work, expected_primary)
        )
    )
    case_state_evidence_available = _case_state_evidence_available(mapped_work)
    missing_state_evidence = bool(case_state_dependent and not case_state_evidence_available)
    explanation_covered = _candidate_explanation_covered(candidate_work)
    return {
        "ranking_scored": ranking_scored,
        "ranking_ambiguous": ranking_ambiguous,
        "expected_primary_operation": expected_primary,
        "ranked_candidate_operations": candidate_operations,
        "case_state_projected_operations": projected_operations,
        "case_state_projection_available": projection_available,
        "case_state_projection_reconstructable": projection_reconstructable,
        "case_state_projected_ranking_match": projected_match,
        "case_state_projected_ranking_ambiguous": projected_ambiguous,
        "case_state_projection_resolved_ambiguity": projection_resolved_ambiguity,
        "expected_primary_present": expected_present,
        "case_state_dependent": case_state_dependent,
        "case_state_evidence_available": case_state_evidence_available,
        "missing_state_evidence": missing_state_evidence,
        "ranking_explanation_covered": explanation_covered,
        "explanation": _ranking_audit_explanation(
            ranking_ambiguous=ranking_ambiguous,
            case_state_dependent=case_state_dependent,
            missing_state_evidence=missing_state_evidence,
        ),
    }


def _candidate_operation_matches(candidate_operations: Sequence[str], expected_operation: str) -> bool:
    for operation in candidate_operations:
        if compare_operational_work_to_expected(
            {"selected_work": {"operation": operation, "category": "", "expected_outcome": ""}},
            {"expected_operation": expected_operation},
        ).get("operation_match"):
            return True
    return False


def _all_candidate_operations_match(candidate_operations: Sequence[str], expected_operations: Sequence[str]) -> bool:
    return all(_candidate_operation_matches(candidate_operations, expected) for expected in expected_operations)


def _all_candidate_operations_with_status(
    candidate_work: Sequence[Mapping[str, Any]],
    expected_operations: Sequence[str],
    *,
    statuses: set[str],
    roles: set[str],
) -> bool:
    for expected in expected_operations:
        matched = False
        for candidate in candidate_work:
            mapped = _mapping(candidate)
            operation = str(mapped.get("operation") or "")
            if not _candidate_operation_matches([operation], expected):
                continue
            status = str(mapped.get("status") or "")
            role = str(mapped.get("work_role") or "")
            if status in statuses or role in roles:
                matched = True
                break
        if not matched:
            return False
    return True


def _candidate_sets_stable(
    previous_candidate_operations: Sequence[str],
    candidate_operations: Sequence[str],
    *,
    selected_operation: str,
) -> bool:
    if selected_operation and _candidate_operation_matches(previous_candidate_operations, selected_operation):
        return True
    previous = {operation for operation in previous_candidate_operations if operation}
    current = {operation for operation in candidate_operations if operation}
    if not previous or not current:
        return False
    overlap = len(previous & current)
    return overlap / max(len(previous | current), 1) >= 0.5


def _candidate_priority_consistent(candidate_work: Sequence[Mapping[str, Any]]) -> bool:
    priorities = [int(_mapping(candidate).get("priority") or 0) for candidate in candidate_work]
    return priorities == sorted(priorities, reverse=True)


def _has_case_state_marker(text: str) -> bool:
    normalized = normalize_text(text)
    return any(
        marker in normalized
        for marker in (
            "ya quedo cargada",
            "ya esta cargada",
            "denuncia ya quedo",
            "denuncia ya esta",
            "faltan documentos",
            "falta documentacion",
            "documentacion completa",
            "ya cargue todo",
            "sigue en tramite",
            "esperando analista",
            "nadie me contacto",
            "nadie me llamo",
            "viene el tecnico",
            "visita tecnica",
            "caso cerrado",
        )
    )


def _has_candidate_state_conflict(candidate_work: Sequence[Mapping[str, Any]], expected_primary: str) -> bool:
    if not candidate_work or not expected_primary:
        return False
    top = _mapping(candidate_work[0])
    top_status = str(top.get("status") or "")
    if top_status not in {"completed", "suspended", "blocked"}:
        return False
    for candidate in candidate_work[1:]:
        operation = str(_mapping(candidate).get("operation") or "")
        if _candidate_operation_matches([operation], expected_primary):
            return True
    return False


def _case_state_evidence_available(mapped_work: Mapping[str, Any]) -> bool:
    projection = _mapping(mapped_work.get("case_state_projection"))
    if projection:
        return True
    evidence = _mapping(mapped_work.get("evidence"))
    if evidence.get("case_state") or evidence.get("operational_case_state"):
        return True
    for candidate in mapped_work.get("candidate_work") or []:
        candidate_evidence = _mapping(_mapping(candidate).get("evidence"))
        if candidate_evidence.get("case_state") or candidate_evidence.get("operational_case_state"):
            return True
        if str(candidate_evidence.get("source") or "") == "case_state":
            return True
    return False


def _candidate_explanation_covered(candidate_work: Sequence[Mapping[str, Any]]) -> bool:
    if not candidate_work:
        return False
    for candidate in candidate_work:
        mapped = _mapping(candidate)
        evidence = _mapping(mapped.get("evidence"))
        if not mapped.get("selection_reason"):
            return False
        if not evidence.get("source"):
            return False
    return True


def _ranking_audit_explanation(
    *,
    ranking_ambiguous: bool,
    case_state_dependent: bool,
    missing_state_evidence: bool,
) -> str:
    if not ranking_ambiguous:
        return "ranking_matched_expected_primary"
    if missing_state_evidence:
        return "expected_primary_present_but_ranked_below_work_that_requires_operational_case_state"
    if case_state_dependent:
        return "ranking_depends_on_case_state_but_evidence_is_available"
    return "expected_primary_present_but_secondary_priority_was_lower"


def _unique_strings(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        item = str(value or "")
        if not item or item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def _is_mixed_intent_turn(turn: Mapping[str, Any]) -> bool:
    multi_work = _mapping(turn.get("multi_work"))
    return bool(multi_work.get("expected_secondary_operations"))


def _real_world_recommendation(metrics: Counter) -> str:
    total = metrics["turn_count"] or 1
    operation_accuracy = _percent(metrics["operation_match"], total)
    transition_accuracy = _percent(metrics["transition_match"], metrics["transition_scored"])
    multi_work = _percent(metrics["multi_work_detected"], metrics["multi_work_scored"])
    if operation_accuracy >= 85 and transition_accuracy >= 80 and multi_work >= 70:
        return "Si: candidate work mapping is strong enough to keep validating operational ranking in shadow mode."
    if operation_accuracy >= 75 and transition_accuracy >= 70:
        return "Parcialmente: keep the mapper in shadow mode and fix multi-work/persistence weaknesses before operational execution."
    return "No: the mapper loses too much consistency on real conversations; correct the model before any planner."


def _is_false_positive(result: Mapping[str, Any]) -> bool:
    comparison = _mapping(result.get("comparison"))
    expected_outcome = str(comparison.get("expected_outcome") or "")
    actual_outcome = str(comparison.get("actual_outcome") or "")
    actual_operation = str(comparison.get("actual_operation") or "")
    if "no_action_required" in expected_outcome:
        return actual_outcome != "no_action_required"
    if actual_operation != "no_operational_work_identified":
        return False
    return bool(comparison.get("expected_operation"))


def _is_conversation_work_confusion(result: Mapping[str, Any]) -> bool:
    comparison = _mapping(result.get("comparison"))
    actual_operation = str(comparison.get("actual_operation") or "")
    expected_category = str(comparison.get("expected_category") or "")
    return actual_operation in {"continue_conversation_plan", "no_operational_work_identified"} and expected_category not in {"administrative", "none"}


def _operational_architecture_takeaway(metrics: Counter, total: int) -> str:
    operation_rate = _percent(metrics["operation_match"], total)
    if operation_rate >= 80 and metrics["impossible_work"] == 0:
        return "The existing Runtime exposes enough state for useful passive work mapping; postpone a full Operational Planner."
    if metrics["impossible_work"]:
        return "The mapper detected unsafe or impossible work suggestions; capability constraints need stronger ownership before execution."
    return "The existing Runtime can be observed operationally, but work selection is not yet reliable enough for an execution model."


def _load_plugin_manifest_catalog(plugin_root: str | Path) -> list[Dict[str, Any]]:
    root = Path(plugin_root)
    if not root.exists():
        return []
    from aca_core.platform_plugins import PluginManifest

    manifests: list[Dict[str, Any]] = []
    for path in sorted(root.glob("*/manifest.yaml")):
        try:
            manifests.append(PluginManifest.from_file(path).to_dict())
        except Exception:
            continue
    return manifests


def _tool_contract_catalog(runtime: Any) -> Dict[str, Any]:
    engine = getattr(runtime, "tool_engine", None)
    contracts = getattr(engine, "_contracts", {}) if engine is not None else {}
    if not isinstance(contracts, Mapping):
        return {}
    return {
        str(name): contract.to_dict() if hasattr(contract, "to_dict") else dict(contract)
        for name, contract in contracts.items()
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
    questions = []
    for match in QUESTION_RE.finditer(response or ""):
        parts = re.split(r"(?<=[.!])\s+", match.group(1).strip())
        question = parts[-1].strip() if parts else match.group(1).strip()
        if question:
            questions.append(question)
    return questions


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
        if not _planned_question_was_asked(
            planned_question=planned_question,
            selected_question=selected_question,
            response_questions=response_questions,
        ):
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


def _has_template_response(response: str) -> bool:
    normalized = normalize_text(response)
    templates = (
        "te puedo orientar paso a paso",
        "nombrame el tramite",
        "contame que parte quedo trabada",
        "te oriento con el tramite",
        "te oriento.",
        "avancemos",
    )
    return any(phrase in normalized for phrase in templates)


def _planned_question_for_response(
    response_plan: Mapping[str, Any],
    selected_question: Mapping[str, Any],
) -> str:
    for item in response_plan.get("required_information") or []:
        if isinstance(item, Mapping) and item.get("question"):
            return str(item["question"])
    return str(selected_question.get("question") or "")


def _count_reformulated_questions(
    *,
    response_plan: Mapping[str, Any],
    info_plan: Mapping[str, Any],
    response_questions: Sequence[str],
) -> int:
    explicit_count = sum(
        1
        for item in response_plan.get("required_information") or []
        if isinstance(item, Mapping) and item.get("question_was_reformulated")
    )
    selected_question = _mapping(info_plan.get("selected_question"))
    planned_question = _planned_question_for_response(response_plan, selected_question)
    if (
        planned_question
        and response_questions
        and _planned_question_was_reformulated(
            planned_question=planned_question,
            selected_question=selected_question,
            response_questions=response_questions,
        )
    ):
        return max(explicit_count, 1)
    return explicit_count


def _planned_question_was_asked(
    *,
    planned_question: str,
    selected_question: Mapping[str, Any],
    response_questions: Sequence[str],
) -> bool:
    expected = _question_signature(planned_question)
    asked = " ".join(_question_signature(question) for question in response_questions)
    if expected and expected in asked:
        return True
    return _response_question_matches_selected_slot(
        selected_question=selected_question,
        response_questions=response_questions,
    )


def _planned_question_was_reformulated(
    *,
    planned_question: str,
    selected_question: Mapping[str, Any],
    response_questions: Sequence[str],
) -> bool:
    expected = _question_signature(planned_question)
    asked = " ".join(_question_signature(question) for question in response_questions)
    if not expected or expected in asked:
        return False
    return _response_question_matches_selected_slot(
        selected_question=selected_question,
        response_questions=response_questions,
    )


def _response_question_matches_selected_slot(
    *,
    selected_question: Mapping[str, Any],
    response_questions: Sequence[str],
) -> bool:
    slot = normalize_text(str(selected_question.get("slot") or ""))
    if not slot:
        return False
    asked = " ".join(_question_signature(question) for question in response_questions)
    semantic_markers = {
        "injuries": (
            ("lesionad", "herid", "atencion medica", "lastimad"),
        ),
        "user_role": (
            ("asegurado", "tercero", "seguro", "poliza", "reclamo", "cobertura", "galicia"),
        ),
        "claim_report_loaded": (
            ("denuncia", "tramite", "siniestro"),
            ("cargad", "cargo", "carga", "iniciad", "hech", "registrad", "finalizar", "finaliz", "quedo"),
        ),
        "documentation_available": (
            ("documentacion", "documento", "documentos", "foto", "fotos", "presupuesto", "captura", "comprobante"),
        ),
    }
    groups = semantic_markers.get(slot)
    if not groups:
        return False
    return all(any(marker in asked for marker in group) for group in groups)


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
