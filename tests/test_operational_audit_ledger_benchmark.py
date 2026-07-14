from aca_os.evaluation import (
    load_operational_audit_ledger_benchmark,
    render_operational_audit_ledger_benchmark_report,
    run_operational_audit_ledger_benchmark,
)


def test_operational_audit_ledger_benchmark_fixture_covers_audit_failures():
    suite = load_operational_audit_ledger_benchmark()

    assert suite["contract"] == "operational_audit_ledger_benchmark_suite.v1"
    assert suite["scenario_count"] >= 10
    assert {
        "double_execution",
        "retry_timeout",
        "partial_response",
        "operation_cancelled",
        "approval_rejected",
        "tool_down",
        "compensable_operation",
        "irreversible_operation",
    }.issubset(set(suite["scenario_types"]))


def test_operational_audit_ledger_benchmark_scores_shadow_ledger():
    result = run_operational_audit_ledger_benchmark(
        scenario_ids=[
            "LEDGER-001",
            "LEDGER-003",
            "LEDGER-004",
            "LEDGER-005",
            "LEDGER-011",
        ]
    )

    assert result["contract"] == "operational_audit_ledger_benchmark_result.v1"
    assert result["scenario_count"] == 5
    assert result["quality"]["ledger_accuracy_percentage"] == 100.0
    assert result["quality"]["ledger_completeness_percentage"] == 100.0
    assert result["quality"]["idempotency_coverage_percentage"] == 100.0
    assert result["quality"]["duplicate_detection_accuracy_percentage"] == 100.0
    assert result["readiness"]["conceptual_completeness_percentage"] == 100.0


def test_operational_audit_ledger_benchmark_report_is_renderable_markdown():
    result = run_operational_audit_ledger_benchmark(scenario_ids=["LEDGER-004"])

    report = render_operational_audit_ledger_benchmark_report(result)

    assert "# ACA Operational Audit Ledger Benchmark" in report
    assert "Ledger completeness" in report
    assert "`LEDGER-004`" in report
    assert "shadow_timeout" in report
