from pathlib import Path

from aca_os.semantic_adversarial_evaluation import (
    ERROR_CLASSIFICATIONS,
    load_adversarial_benchmark,
    render_adversarial_semantic_report,
    run_adversarial_semantic_evaluation,
)


REQUIRED_CATEGORIES = {
    "irony",
    "sarcasm",
    "humor",
    "double_negation",
    "triple_negation",
    "multiple_corrections",
    "successive_retraction",
    "ambiguous_reference",
    "context_jump",
    "extreme_length",
    "short_message",
    "orthography",
    "whatsapp",
    "emoji",
    "audio_transcript",
    "distributed_information",
    "distant_memory",
    "conflicting_priorities",
    "multiple_interlocutors",
    "cross_reference",
    "real_ambiguity",
}


def test_adversarial_corpus_is_independent_large_and_stressful():
    benchmark = load_adversarial_benchmark()
    categories = {
        category
        for conversation in benchmark["conversations"]
        for turn in conversation["turns"]
        for category in turn["categories"]
    }

    assert benchmark["contract"] == "semantic_adversarial_benchmark.v1"
    assert benchmark["conversation_count"] == 100
    assert benchmark["turn_count"] > 1000
    assert benchmark["official_message_overlap_count"] == 0
    assert benchmark["long_message_count"] == 10
    assert benchmark["maximum_message_words"] > 2000
    assert benchmark["stress_conversation_count"] == 10
    assert benchmark["maximum_conversation_turns"] > 50
    assert REQUIRED_CATEGORIES <= categories
    assert len(benchmark["benchmark_hash"]) == 64


def test_evaluator_is_offline_passive_and_does_not_import_runtime():
    module_path = (
        Path(__file__).resolve().parents[1]
        / "aca_os"
        / "semantic_adversarial_evaluation.py"
    )
    source = module_path.read_text(encoding="utf-8")

    assert "from aca_os.runtime import" not in source
    assert "import aca_os.runtime" not in source
    assert "ACAOSRuntime(" not in source
    assert "ConversationState(" not in source


def test_evaluation_exposes_robustness_errors_and_calibration():
    result = run_adversarial_semantic_evaluation(
        profile_ids=["ambiguous_cross_reference"],
        compare_official=False,
    )

    assert result["engine"]["mode"] == "shadow"
    assert result["engine"]["official_authority"] == "legacy"
    assert result["engine"]["runtime_used"] is False
    assert result["engine"]["decision_influence"] is False
    assert result["engine"]["state_mutation"] is False
    assert result["engine"]["provider_calls"] == 0
    assert {
        "semantic_robustness_score",
        "semantic_stability",
        "consistency_score",
        "recovery_score",
        "context_retention",
        "long_conversation_accuracy",
        "noise_resistance",
        "ambiguity_robustness",
    } <= set(result["metrics"])
    assert {
        "mean_confidence",
        "mean_turn_score",
        "mean_absolute_calibration_error",
        "overconfident_error_count",
    } <= set(result["confidence_calibration"])
    assert all(
        {"expected", "actual", "difference", "classification", "severity"} <= set(error)
        for conversation in result["conversations"]
        for turn in conversation["turns"]
        for error in turn["errors"]
    )


def test_full_red_team_generates_top_100_and_every_error_bucket():
    result = run_adversarial_semantic_evaluation(compare_official=False)

    assert result["metrics"]["evaluated_conversation_count"] == 100
    assert result["metrics"]["evaluated_turn_count"] == 1230
    assert len(result["worst_cases"]) == 100
    assert [item["rank"] for item in result["worst_cases"]] == list(range(1, 101))
    assert set(result["error_classification"]["counts"]) == set(ERROR_CLASSIFICATIONS)
    assert result["error_classification"]["total_errors"] > 0
    assert result["recommendation"]["decision"] in {
        "CONTROLLED_MIGRATION_READY",
        "LOW_RISK_VERTICAL_PILOT_ONLY",
        "NOT_READY_FOR_SA3",
    }


def test_adversarial_result_is_reproducible():
    first = run_adversarial_semantic_evaluation(
        profile_ids=["pragmatic_noise"], compare_official=False
    )
    second = run_adversarial_semantic_evaluation(
        profile_ids=["pragmatic_noise"], compare_official=False
    )

    assert first["report_hash"] == second["report_hash"]
    assert first["metrics"] == second["metrics"]
    assert first["error_classification"] == second["error_classification"]
    assert first["reproducibility"]["deterministic"] is True


def test_official_comparison_uses_the_unchanged_benchmark():
    result = run_adversarial_semantic_evaluation(
        profile_ids=["pragmatic_noise"], compare_official=True
    )
    comparison = result["benchmark_comparison"]

    assert comparison["official_benchmark_hash"] == (
        "79c644695143252969f4dde4e4e94b6dbabe6c7813c6733ddaed5340057ac5bd"
    )
    assert comparison["official_semantic_score"] == 0.9865
    assert comparison["official_message_overlap_count"] == 0
    assert comparison["official_authority"] == "legacy"


def test_markdown_report_contains_red_team_decision_layers():
    result = run_adversarial_semantic_evaluation(
        profile_ids=["real_ambiguity_and_successive_retraction"],
        compare_official=False,
    )
    report = render_adversarial_semantic_report(result)

    assert "# Semantic Authority Adversarial Validation" in report
    assert "## Official vs Adversarial" in report
    assert "## Robustness" in report
    assert "## Confidence Calibration" in report
    assert "## Error Classification" in report
    assert "## Worst Conversations" in report
    assert "## Promotion Recommendation" in report
    assert "Legacy remains the only effective authority" in report
