from pathlib import Path

from aca_os.semantic_understanding_evaluation import (
    REQUIRED_DASHBOARD_METRICS,
    load_semantic_understanding_benchmark,
    render_semantic_understanding_report,
    run_semantic_understanding_evaluation,
)


REQUIRED_CATEGORIES = {
    "entities",
    "person",
    "organization",
    "place",
    "object",
    "pet",
    "service",
    "product",
    "explicit_fact",
    "negative_fact",
    "temporal",
    "conditional_fact",
    "negation",
    "correction",
    "retraction",
    "memory",
    "topic_shift",
    "multi_topic",
    "priority",
    "coreference",
    "contradiction",
    "ambiguity",
}


def test_benchmark_is_permanent_large_and_non_repeated():
    benchmark = load_semantic_understanding_benchmark()
    categories = {
        category
        for conversation in benchmark["conversations"]
        for turn in conversation["turns"]
        for category in turn["categories"]
    }

    assert benchmark["contract"] == "semantic_understanding_benchmark.v1"
    assert benchmark["profile_count"] == 10
    assert benchmark["conversation_count"] >= 100
    assert benchmark["turn_count"] > 500
    assert benchmark["unique_message_count"] == benchmark["turn_count"]
    assert REQUIRED_CATEGORIES <= categories
    assert benchmark["context_policy"] == "teacher_forced_prior_gold"
    assert len(benchmark["benchmark_hash"]) == 64


def test_evaluator_is_offline_and_does_not_import_runtime():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "aca_os"
        / "semantic_understanding_evaluation.py"
    )
    source = module_path.read_text(encoding="utf-8")

    assert "from aca_os.runtime import" not in source
    assert "import aca_os.runtime" not in source
    assert "ACAOSRuntime(" not in source
    assert "ConversationState(" not in source


def test_evaluation_is_passive_inspectable_and_complete_for_a_conversation():
    result = run_semantic_understanding_evaluation(
        conversation_ids=["insurance_negation_contradiction:01"]
    )

    assert result["contract"] == "semantic_understanding_evaluation_result.v1"
    assert result["benchmark"]["conversation_count"] == 1
    assert result["benchmark"]["turn_count"] == 6
    assert result["engine"] == {
        "component": "semantic_authority",
        "version": result["engine"]["version"],
        "mode": "shadow",
        "runtime_used": False,
        "decision_influence": False,
        "state_mutation": False,
    }
    assert set(REQUIRED_DASHBOARD_METRICS) == {
        item["metric"] for item in result["dashboard"]
    }
    assert all(
        {"expected", "actual", "difference", "category", "severity"} <= set(error)
        for error in result["errors"]
    )
    assert all(
        turn["expected"] is not None and turn["actual"] is not None
        for conversation in result["conversations"]
        for turn in conversation["turns"]
    )


def test_evaluation_is_reproducible():
    first = run_semantic_understanding_evaluation(
        conversation_ids=["corrections:01", "coreference:01"]
    )
    second = run_semantic_understanding_evaluation(
        conversation_ids=["corrections:01", "coreference:01"]
    )

    assert first["report_hash"] == second["report_hash"]
    assert first["summary"] == second["summary"]
    assert first["errors"] == second["errors"]
    assert first["reproducibility"]["deterministic"] is True
    assert first["reproducibility"]["provider_calls"] == 0
    assert first["reproducibility"]["runtime_calls"] == 0


def test_full_evaluation_covers_every_benchmark_turn():
    result = run_semantic_understanding_evaluation()

    assert result["benchmark"]["profile_count"] == 10
    assert result["benchmark"]["conversation_count"] == 100
    assert result["benchmark"]["turn_count"] == 600
    assert result["benchmark"]["unique_message_count"] == 600
    assert len(result["conversations"]) == 100
    assert sum(len(item["turns"]) for item in result["conversations"]) == 600
    assert result["summary"]["semantic_understanding_score"] is not None
    assert len(result["report_hash"]) == 64


def test_markdown_report_contains_every_reporting_layer():
    result = run_semantic_understanding_evaluation(
        profile_ids=["ambiguity_uncertainty"]
    )
    report = render_semantic_understanding_report(result)

    assert "# ACA Semantic Understanding Evaluation" in report
    assert "## Dashboard" in report
    assert "## Results By Category" in report
    assert "## Results By Conversation" in report
    assert "## Results By Turn" in report
    assert "## Frequent Errors" in report
    assert "## Error Distribution" in report
    assert "SemanticAuthority mode: `shadow`" in report
    assert "Runtime used: `false`" in report
