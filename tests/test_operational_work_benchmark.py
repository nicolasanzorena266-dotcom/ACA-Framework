from aca_os.evaluation import (
    load_operational_work_benchmark,
    render_operational_work_benchmark_report,
    run_operational_work_benchmark,
)


def test_operational_benchmark_fixture_contains_50_work_scenarios():
    suite = load_operational_work_benchmark()

    assert suite["contract"] == "operational_work_benchmark_suite.v1"
    assert suite["scenario_count"] == 50
    assert suite["turn_count"] == 50
    assert {
        "informational_query",
        "follow_up",
        "billing",
        "technical_support",
        "claim",
        "documentation",
        "coordination",
        "delegation",
        "service_recovery",
        "multiple_needs",
        "goal_shift",
        "ambiguous_user",
        "hostile_user",
    }.issubset(set(suite["scenario_types"]))


def test_operational_work_benchmark_runs_real_runtime_in_shadow_mode():
    result = run_operational_work_benchmark(
        scenario_ids=[
            "OB-003",
            "OB-004",
            "OB-026",
            "OB-046",
        ]
    )

    assert result["contract"] == "operational_work_benchmark_result.v1"
    assert result["scenario_count"] == 4
    assert result["quality"]["work_identified_percentage"] == 100.0
    assert result["quality"]["correct_operation_selection_percentage"] == 100.0
    assert result["quality"]["impossible_work_percentage"] == 0.0
    assert result["architecture"]["mapper_mode"] == "shadow"
    assert result["architecture"]["runtime_mutations"] == 0
    assert result["architecture"]["response_changes"] == 0
    assert all(scenario["mapped_work"]["changes_response"] is False for scenario in result["scenarios"])


def test_operational_work_benchmark_report_is_renderable_markdown():
    result = run_operational_work_benchmark(scenario_ids=["OB-004"])

    report = render_operational_work_benchmark_report(result)

    assert "# ACA Operational Work Benchmark" in report
    assert "## Quality" in report
    assert "`OB-004`" in report
    assert "prepare_claim_follow_up" in report
