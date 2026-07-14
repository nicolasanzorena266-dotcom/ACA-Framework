from aca_os.evaluation import (
    load_operational_dry_run_benchmark,
    render_operational_dry_run_benchmark_report,
    run_operational_dry_run_benchmark,
)
from aca_os.operational_tools import HandoffPackageDryRunAdapter
from aca_os.tool_engine import (
    ToolEngine,
    ToolExecutionContext,
    ToolExecutionMode,
    ToolRequest,
)


def test_handoff_package_tool_supports_dry_run_without_side_effects():
    engine = ToolEngine()
    engine.register(HandoffPackageDryRunAdapter())

    result = engine.execute(
        ToolRequest(
            tool_name="handoff_package",
            intent="prepare_handoff_package",
            payload={
                "conversation_id": "dry-run-test",
                "selected_work": {"operation": "prepare_handoff"},
                "governance_assessment": {"execution_allowed": True},
                "ledger_record": {"conversation_id": "dry-run-test"},
            },
        ),
        ToolExecutionContext(mode=ToolExecutionMode.DRY_RUN, runtime_engine="runtime_executor"),
    )

    receipt = result.evidence["projected_receipt"]
    assert result.success is True
    assert result.execution["action"] == "dry_run"
    assert result.execution["executed"] is False
    assert receipt["status"] == "dry_run_completed"
    assert receipt["side_effects"] is False
    assert receipt["external_write"] is False


def test_operational_dry_run_benchmark_loads_realistic_handoff_scenarios():
    suite = load_operational_dry_run_benchmark()

    assert suite["contract"] == "operational_dry_run_benchmark_suite.v1"
    assert suite["scenario_count"] >= 30
    assert suite["tool"] == "handoff_package"
    assert suite["operation"] == "prepare_handoff"


def test_operational_dry_run_benchmark_executes_complete_chain():
    result = run_operational_dry_run_benchmark(
        scenario_ids=["DRY-001", "DRY-008", "DRY-021", "DRY-030"]
    )

    assert result["contract"] == "operational_dry_run_benchmark_result.v1"
    assert result["scenario_count"] == 4
    assert result["quality"]["end_to_end_success_percentage"] == 100.0
    assert result["quality"]["candidate_tool_coherence_percentage"] == 100.0
    assert result["quality"]["governance_pass_percentage"] == 100.0
    assert result["quality"]["ledger_completeness_percentage"] == 100.0
    assert result["quality"]["receipt_generated_percentage"] == 100.0
    assert result["quality"]["side_effect_free_percentage"] == 100.0
    assert result["quality"]["replay_consistency_percentage"] == 100.0
    assert result["architecture"]["visible_response_changes"] is False


def test_operational_dry_run_benchmark_report_is_renderable_markdown():
    result = run_operational_dry_run_benchmark(scenario_ids=["DRY-001"])

    report = render_operational_dry_run_benchmark_report(result)

    assert "# ACA Operational Dry Run Benchmark" in report
    assert "End-to-end success" in report
    assert "`DRY-001`" in report
    assert "dry_run_completed" in report
