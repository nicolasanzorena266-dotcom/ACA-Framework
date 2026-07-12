from aca_os.evaluation import (
    REQUIRED_BENCHMARK_TAGS,
    load_conversation_benchmark,
    render_cognitive_benchmark_report,
    run_cognitive_conversation_benchmark,
)


def test_cognitive_benchmark_fixture_covers_required_conversation_capabilities():
    suite = load_conversation_benchmark()

    assert suite["contract"] == "conversation_benchmark_suite.v1"
    assert suite["scenario_count"] >= 18
    assert suite["turn_count"] >= 40
    assert set(REQUIRED_BENCHMARK_TAGS).issubset(set(suite["tags"]))
    assert suite["missing_required_tags"] == []


def test_cognitive_benchmark_runs_real_runtime_and_records_cognitive_metrics():
    result = run_cognitive_conversation_benchmark(
        scenario_ids=[
            "prioridad_fotos_vs_reparacion",
            "interrupcion_lateral_tiempos",
            "correccion_lesionados",
        ]
    )

    assert result["contract"] == "cognitive_evaluation_benchmark_result.v1"
    assert result["scenario_count"] == 3
    assert result["turn_count"] == 8
    assert result["quality"]["questions_asked"] > 0
    assert result["quality"]["questions_avoided"] >= 1
    assert result["quality"]["conversation_plan_used_turns"] >= 3
    assert result["quality"]["response_plan_used_turns"] >= 3
    assert result["quality"]["facts_used_turns"] >= 1
    assert "template_response_count" in result["quality"]
    assert "runtime_executor" in result["quality"]["runtime_engines"]


def test_cognitive_benchmark_validates_narrative_response_quality():
    result = run_cognitive_conversation_benchmark(
        scenario_ids=[
            "narrativa_denuncia_en_tramite",
            "narrativa_recupera_ya_te_lo_dije",
        ]
    )

    assert result["scenario_count"] == 2
    assert result["errors"]["count"] == 0
    assert result["quality"]["template_response_count"] == 0
    assert result["quality"]["repeated_question_count"] == 0


def test_cognitive_benchmark_audits_contract_value_and_unused_complexity():
    result = run_cognitive_conversation_benchmark(
        scenario_ids=[
            "prioridad_fotos_vs_reparacion",
            "tiempos_contacto",
        ]
    )
    architecture = result["architecture"]

    assert "conversation_response_plan" in architecture["value_contributing_contracts"]
    assert "conversation_information_gain_plan" in architecture["value_contributing_contracts"]
    assert architecture["contracts_never_used"]
    assert architecture["complexity_without_observed_benefit"]
    assert architecture["critical_takeaway"]


def test_cognitive_benchmark_report_is_renderable_markdown():
    result = run_cognitive_conversation_benchmark(
        scenario_ids=["prioridad_fotos_vs_reparacion"]
    )

    report = render_cognitive_benchmark_report(result)

    assert "# ACA Cognitive Conversation Benchmark" in report
    assert "## Coverage" in report
    assert "## Quality" in report
    assert "## Architecture" in report
    assert "`prioridad_fotos_vs_reparacion`" in report
