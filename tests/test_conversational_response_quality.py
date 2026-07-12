from aca_kernel.core.events import Event
from aca_os.conversation_state import conversational_response_plan_contract
from sdk.factory import build_galicia_runtime


FORBIDDEN_META = (
    "no voy",
    "no te vuelvo",
    "para no girar",
    "cambiar de estrategia",
    "mision actual",
    "sin reiniciar",
    "dejo suspendido",
)


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _plan(state):
    return state.facts["conversation_response_plan"]["plan"]


def _assert_no_meta(response: str):
    normalized = response.lower()
    for phrase in FORBIDDEN_META:
        assert phrase not in normalized


def test_conversational_response_plan_contract_is_explicit():
    contract = conversational_response_plan_contract()

    assert contract["contract"] == "conversational_response_plan.v1"
    assert "primary_user_need" in contract["required_fields"]
    assert "dominant_concern" in contract["required_fields"]
    assert "required_information" in contract["required_fields"]
    assert contract["principles"]["cognitive_opacity"]
    assert contract["principles"]["question_justification"]


def test_multiple_needs_prioritize_dominant_user_concern_before_secondary_need():
    runtime = build_galicia_runtime()
    _run(runtime, "quality-multi", "Me chocaron ayer")

    state = _run(
        runtime,
        "quality-multi",
        "No se si mande las fotos, pero lo que mas me preocupa es si puedo arreglar el auto.",
    )
    plan = _plan(state)

    assert plan["primary_user_need"]["key"] == "vehicle_repair_authorization"
    assert plan["secondary_needs"][0]["key"] == "photo_upload_status"
    assert plan["dominant_concern"]["key"] == "vehicle_repair_authorization"
    assert plan["response_priority"][:2] == ["vehicle_repair_authorization", "photo_upload_status"]
    assert state.response.index("arreglar el auto") < state.response.index("fotos")
    _assert_no_meta(state.response)


def test_dominant_concern_is_addressed_before_procedure():
    runtime = build_galicia_runtime()

    state = _run(runtime, "quality-concern", "Me preocupa si puedo arreglar el auto.")
    plan = _plan(state)

    assert plan["primary_user_need"]["key"] == "vehicle_repair_authorization"
    assert plan["dominant_concern"]["source"] == "conversation_intent_model"
    assert state.response.startswith("Sobre arreglar el auto")
    assert "Que necesitas resolver primero" not in state.response
    _assert_no_meta(state.response)


def test_questions_have_explicit_justification_in_plan_and_response():
    runtime = build_galicia_runtime()

    state = _run(runtime, "quality-question", "Me chocaron ayer")
    plan = _plan(state)
    required = plan["required_information"][0]

    assert required["slot"] == "injuries"
    assert required["question"] == "Hubo lesionados?"
    assert required["purpose"] == "definir si corresponde priorizar asistencia o derivacion antes del tramite"
    assert "Hubo lesionados?" in state.response
    assert "Asi puedo definir si corresponde priorizar asistencia" in state.response
    _assert_no_meta(state.response)


def test_response_quality_observability_is_introspection_only_not_user_facing():
    runtime = build_galicia_runtime()
    _run(runtime, "quality-observable", "Me chocaron ayer")
    state = _run(
        runtime,
        "quality-observable",
        "No se si mande las fotos, pero lo que mas me preocupa es si puedo arreglar el auto.",
    )
    trace = state.facts["conversation_response_plan"]

    assert trace["primary_user_need"]["key"] == "vehicle_repair_authorization"
    assert trace["dominant_concern"]["key"] == "vehicle_repair_authorization"
    assert trace["question_justifications"]
    assert "conversation_response_plan" not in state.response
    assert "response_priority" not in state.response
    _assert_no_meta(state.response)
