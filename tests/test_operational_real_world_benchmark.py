from aca_os.evaluation import (
    load_operational_real_world_benchmark,
    render_operational_real_world_benchmark_report,
    run_operational_real_world_benchmark,
)


def test_operational_real_world_fixture_uses_existing_development_conversations():
    suite = load_operational_real_world_benchmark()

    assert suite["contract"] == "operational_real_world_benchmark_suite.v1"
    assert suite["conversation_count"] >= 56
    assert suite["turn_count"] >= 90
    assert any(source.startswith("benchmarks/conversations/") for source in suite["sources"])
    assert "historical_roleplay_sprint_76" in suite["sources"]


def test_operational_real_world_benchmark_scores_transitions_and_multi_work():
    result = run_operational_real_world_benchmark(
        conversation_ids=[
            "RW-002",
            "RW-010",
            "RW-012",
        ]
    )

    assert result["contract"] == "operational_real_world_benchmark_result.v1"
    assert result["conversation_count"] == 3
    assert result["turn_count"] == 14
    assert result["quality"]["work_transition_accuracy_percentage"] == 100.0
    assert result["quality"]["work_persistence_error_count"] == 0
    assert result["quality"]["multi_work_detection_percentage"] == 100.0
    assert result["quality"]["candidate_work_recall_percentage"] == 100.0
    assert result["quality"]["secondary_work_detection_percentage"] == 100.0
    assert result["quality"]["work_ranking_accuracy_percentage"] == 100.0
    assert result["quality"]["ranking_explanation_coverage_percentage"] == 100.0
    assert result["errors"]["counts"] == {}
    assert result["architecture"]["mapper_mode"] == "shadow"
    assert result["architecture"]["runtime_mutations"] == 0
    assert result["architecture"]["response_changes"] == 0


def test_operational_real_world_report_is_renderable_markdown():
    result = run_operational_real_world_benchmark(conversation_ids=["RW-010"])

    report = render_operational_real_world_benchmark_report(result)

    assert "# ACA Operational Real-World Benchmark" in report
    assert "Work transition accuracy" in report
    assert "Candidate work recall" in report
    assert "Ranking ambiguity rate" in report
    assert "Case-state projected ranking accuracy" in report
    assert "`RW-010`" in report
    assert "Recommendation" in report


def test_operational_real_world_benchmark_exposes_case_state_ranking_gap():
    result = run_operational_real_world_benchmark(conversation_ids=["RW-051"])
    turn = result["conversations"][0]["turns"][0]

    assert result["quality"]["candidate_work_recall_percentage"] == 100.0
    assert result["quality"]["work_ranking_accuracy_percentage"] == 0.0
    assert result["quality"]["ranking_ambiguity_rate_percentage"] == 100.0
    assert result["quality"]["case_state_dependency_rate_percentage"] == 100.0
    assert result["quality"]["missing_state_evidence_count"] == 0
    assert result["quality"]["case_state_projection_available_percentage"] == 100.0
    assert result["quality"]["case_state_projection_reconstructable_percentage"] == 100.0
    assert result["quality"]["case_state_projected_ranking_accuracy_percentage"] == 100.0
    assert result["quality"]["case_state_projected_ranking_ambiguity_rate_percentage"] == 0.0
    assert result["quality"]["case_state_projection_resolved_ambiguity_count"] == 1
    assert result["quality"]["unresolved_projected_ranking_error_count"] == 0
    assert result["quality"]["ranking_explanation_coverage_percentage"] == 100.0
    assert turn["ranking_audit"]["expected_primary_present"] is True
    assert turn["ranking_audit"]["missing_state_evidence"] is False
    assert turn["ranking_audit"]["case_state_projection_resolved_ambiguity"] is True
