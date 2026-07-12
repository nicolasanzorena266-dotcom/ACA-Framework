from aca_kernel.core.events import Event
from aca_os.evaluation import run_cognitive_conversation_benchmark
from sdk.factory import build_galicia_runtime


FORBIDDEN_USER_LANGUAGE = (
    "sin reiniciar",
    "mantengo el foco",
    "mision activa",
    "conversation plan",
    "conversation goal",
    "slot",
    "estado conversacional",
    "runtime",
    "planificacion",
    "check_claim_report_loaded",
)


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _assert_no_internal_language(response: str):
    normalized = response.lower()
    for phrase in FORBIDDEN_USER_LANGUAGE:
        assert phrase not in normalized


def test_ambiguous_answer_reformulates_instead_of_repeating_question():
    runtime = build_galicia_runtime()
    _run(runtime, "quality-reformulate", "Me chocaron ayer")

    state = _run(runtime, "quality-reformulate", "No estoy seguro.")
    required = state.facts["conversation_response_plan"]["plan"]["required_information"][0]

    assert "Hubo lesionados?" not in state.response
    assert "lastimado" in state.response or "herida" in state.response or "atencion medica" in state.response
    assert required["question_was_reformulated"] is True
    assert required["reformulated_from"] == "Hubo lesionados?"


def test_answered_question_is_not_asked_again():
    runtime = build_galicia_runtime()
    _run(runtime, "quality-no-repeat-answered", "Me chocaron ayer")

    state = _run(runtime, "quality-no-repeat-answered", "No hubo lesionados.")

    assert "Hubo lesionados?" not in state.response
    assert "sos asegurado" in state.response.lower()


def test_lateral_question_is_answered_before_requesting_more_information_and_resumes_topic():
    runtime = build_galicia_runtime()
    _run(runtime, "quality-lateral", "Me chocaron ayer")
    _run(runtime, "quality-lateral", "No hubo lesionados.")

    state = _run(runtime, "quality-lateral", "Y cuanto tarda normalmente?")

    assert state.response.index("Sobre cuando te van a contactar") < state.response.index("Respecto a tu denuncia")
    assert "Respecto a tu denuncia" in state.response
    assert "sos asegurado" in state.response.lower()


def test_simplification_does_not_leak_cognitive_opacity_or_restart_with_question():
    runtime = build_galicia_runtime()
    _run(runtime, "quality-simple", "Me explicas que pasa si arreglo el auto antes de que me autoricen?")

    state = _run(runtime, "quality-simple", "Explicamelo mas simple, por favor.")

    assert state.response.startswith("Mas simple:")
    assert "Que punto queres resolver primero" not in state.response
    _assert_no_internal_language(state.response)


def test_benchmark_quality_metrics_capture_regression_targets():
    result = run_cognitive_conversation_benchmark(
        scenario_ids=[
            "respuesta_parcial",
            "interrupcion_lateral_tiempos",
            "profundizacion",
        ]
    )

    assert result["quality"]["opacity_leaks"] == 0
    assert result["quality"]["repeated_question_count"] == 0
    assert result["quality"]["reformulated_questions"] >= 2
    assert result["quality"]["answered_before_asking"] >= 1
    assert result["quality"]["resumed_topic_success"] >= 1
