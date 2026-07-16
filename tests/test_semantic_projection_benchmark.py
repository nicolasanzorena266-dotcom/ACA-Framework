from aca_os.semantic_projection_evaluation import (
    load_semantic_projection_benchmark,
    render_semantic_projection_benchmark_report,
    run_semantic_projection_benchmark,
)


def test_semantic_projection_benchmark_contains_required_real_conversation_cases():
    suite = load_semantic_projection_benchmark()
    scenarios = suite["scenarios"]
    tags = {tag for scenario in scenarios for tag in scenario.get("tags") or []}

    assert suite["contract"] == "semantic_projection_shadow_benchmark_suite.v1"
    assert len(scenarios) >= 10
    assert {"negation", "correction", "retraction", "topic_shift", "memory", "multiple_topics"} <= tags


def test_semantic_projection_benchmark_runs_real_runtime_in_passive_shadow(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    result = run_semantic_projection_benchmark()

    assert result["contract"] == "semantic_projection_shadow_benchmark_result.v1"
    assert result["passed"] is True
    assert result["scenario_count"] == 10
    assert result["turn_count"] >= 13
    assert result["complete_projection_turn_count"] == result["turn_count"]
    assert result["observation_failure_count"] == 0
    assert result["architecture"]["official_authority"] == "legacy"
    assert result["architecture"]["semantic_projection_mode"] == "shadow"
    assert result["architecture"]["authority_violation_count"] == 0
    assert result["architecture"]["decision_influence_count"] == 0
    assert result["architecture"]["state_mutation_count"] == 0
    assert result["projection_status_counts"]
    assert set(result["metrics"]) == {
        "entity_precision",
        "entity_recall",
        "fact_precision",
        "fact_recall",
        "goal_agreement",
        "intent_agreement",
        "slot_precision",
        "slot_recall",
        "topic_agreement",
    }
    assert all(turn["legacy_projection"] for scenario in result["scenarios"] for turn in scenario["turns"])
    assert all(turn["semantic_projection"] for scenario in result["scenarios"] for turn in scenario["turns"])
    assert all(turn["projection_diff"] for scenario in result["scenarios"] for turn in scenario["turns"])


def test_semantic_projection_benchmark_report_is_renderable(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    result = run_semantic_projection_benchmark(scenario_ids=["SP-003", "SP-004"])
    report = render_semantic_projection_benchmark_report(result)

    assert "# ACA Semantic Projection Shadow Benchmark" in report
    assert "Official authority: `legacy`" in report
    assert "Decision influence: `0`" in report
    assert "Entity Recall Percentage" in report
