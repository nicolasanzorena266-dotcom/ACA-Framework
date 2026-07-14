from aca_os.evaluation import (
    load_operational_governance_benchmark,
    render_operational_governance_benchmark_report,
    run_operational_governance_benchmark,
)


def test_operational_governance_benchmark_fixture_covers_governance_risks():
    suite = load_operational_governance_benchmark()

    assert suite["contract"] == "operational_governance_benchmark_suite.v1"
    assert suite["scenario_count"] >= 12
    assert {
        "external_write",
        "tool_unavailable",
        "double_execution",
        "missing_evidence",
        "financial_adjustment",
        "identity_sensitive",
        "irreversible",
        "permission",
    }.issubset(set(suite["scenario_types"]))


def test_operational_governance_benchmark_scores_shadow_gate():
    result = run_operational_governance_benchmark(
        scenario_ids=[
            "GOV-001",
            "GOV-003",
            "GOV-004",
            "GOV-009",
            "GOV-016",
        ]
    )

    assert result["contract"] == "operational_governance_benchmark_result.v1"
    assert result["scenario_count"] == 5
    assert result["quality"]["governance_accuracy_percentage"] == 100.0
    assert result["quality"]["unsafe_execution_detection_percentage"] == 100.0
    assert result["quality"]["governance_false_positive_count"] == 0
    assert result["quality"]["governance_false_negative_count"] == 0
    assert result["readiness"]["requires_confirmation_count"] >= 3
    assert result["readiness"]["requires_human_approval_count"] >= 1
    assert result["readiness"]["immediate_enablement_percentage"] > 0


def test_operational_governance_benchmark_report_is_renderable_markdown():
    result = run_operational_governance_benchmark(scenario_ids=["GOV-004"])

    report = render_operational_governance_benchmark_report(result)

    assert "# ACA Operational Governance Benchmark" in report
    assert "Governance accuracy" in report
    assert "`GOV-004`" in report
    assert "open_ticket" in report
