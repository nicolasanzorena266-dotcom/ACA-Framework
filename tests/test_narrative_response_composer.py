from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.narrative_response_composer import NarrativeResponseComposer
from sdk.factory import build_galicia_runtime


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def test_narrative_composer_turns_claim_delay_state_into_natural_response():
    runtime = build_galicia_runtime()

    state = _run(
        runtime,
        "narrative-delay",
        "Cargue una denuncia desde la app y hace una semana sigue en tramite.",
    )

    assert state.response.startswith("Entiendo.")
    assert "una semana" in state.response
    assert "que esta demorando el avance del caso" in state.response
    assert "Recordas si alguna persona resulto herida" in state.response
    assert "Hubo lesionados?" not in state.response
    assert "Nombrame el tramite" not in state.response
    assert "Te oriento" not in state.response


def test_narrative_composer_acknowledges_repetition_with_known_facts():
    runtime = build_galicia_runtime()
    _run(runtime, "narrative-repetition", "Me chocaron ayer")
    _run(runtime, "narrative-repetition", "No hubo lesionados.")

    state = _run(runtime, "narrative-repetition", "Ya te lo dije.")

    assert state.response.startswith("Tenes razon")
    assert "no hubo lesionados" in state.response
    assert "estado de la denuncia" in state.response
    assert "seguro Galicia es tuyo" in state.response
    assert "Nombrame el tramite" not in state.response
    assert "Te puedo orientar paso a paso" not in state.response


def test_narrative_composer_preserves_specialized_tool_responses():
    state = CognitiveState(
        response="CLEAS: captured from official execution",
        selected_program="knowledge_lookup",
        facts={"zero_cost_execution_plan": {"flow": "knowledge_lookup"}},
    )

    result = NarrativeResponseComposer().compose(
        state=state,
        event=Event(type="user_message", payload="Que es CLEAS?"),
    )

    assert result.response == "CLEAS: captured from official execution"
    assert result.changed is False
