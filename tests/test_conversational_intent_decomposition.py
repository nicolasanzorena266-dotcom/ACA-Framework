from aca_kernel.core.events import Event
from aca_os.conversation_state import conversational_intent_model_contract
from sdk.factory import build_galicia_runtime


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _intent_model(state):
    return state.facts["conversation_intent_model"]["model"]


def _response_plan(state):
    return state.facts["conversation_response_plan"]["plan"]


def test_conversational_intent_model_contract_is_explicit():
    contract = conversational_intent_model_contract()

    assert contract["contract"] == "conversational_intent_model.v1"
    assert contract["required_fields"] == [
        "explicit_questions",
        "implicit_questions",
        "dominant_concern",
        "user_goal",
        "user_assumptions",
        "missing_information",
        "response_objective",
    ]


def test_vehicle_repair_question_infers_claim_risk_without_explicit_marker():
    runtime = build_galicia_runtime()

    state = _run(runtime, "intent-repair", "Puedo arreglar el auto?")
    model = _intent_model(state)
    plan = _response_plan(state)

    assert model["explicit_questions"][0]["key"] == "can_repair_vehicle"
    assert model["implicit_questions"][0]["key"] == "repair_affects_claim"
    assert model["dominant_concern"]["key"] == "preserve_claim_while_repairing_vehicle"
    assert model["user_assumptions"][0]["key"] == "early_repair_may_affect_claim"
    assert {item["key"] for item in model["missing_information"]} >= {
        "claim_authorization_status",
        "damage_evidence_available",
    }
    assert plan["primary_user_need"]["key"] == "vehicle_repair_authorization"
    assert plan["dominant_concern"]["source"] == "conversation_intent_model"
    assert "no perjudicar la evaluacion" in state.response


def test_contact_timing_question_models_process_progress_concern():
    runtime = build_galicia_runtime()

    state = _run(runtime, "intent-contact", "Cuando me van a contactar?")
    model = _intent_model(state)
    plan = _response_plan(state)

    assert model["explicit_questions"][0]["key"] == "when_will_contact_me"
    assert model["implicit_questions"][0]["key"] == "case_following_process"
    assert model["dominant_concern"]["key"] == "case_may_not_be_progressing"
    assert plan["primary_user_need"]["key"] == "claim_contact_progress"
    assert "siguiendo el circuito esperado" in state.response


def test_no_photo_request_models_did_i_miss_a_step_concern():
    runtime = build_galicia_runtime()

    state = _run(runtime, "intent-photos", "No me pidieron las fotos.")
    model = _intent_model(state)
    plan = _response_plan(state)

    assert model["explicit_questions"][0]["key"] == "photos_not_requested"
    assert model["implicit_questions"][0]["key"] == "missed_required_step"
    assert model["dominant_concern"]["key"] == "missed_photo_step"
    assert plan["primary_user_need"]["key"] == "photo_requirement_confidence"
    assert "no significa necesariamente que hiciste algo mal" in state.response


def test_multiple_questions_use_implicit_concern_without_dominant_marker():
    runtime = build_galicia_runtime()

    state = _run(runtime, "intent-multi", "No se si mande las fotos. Puedo arreglar el auto?")
    model = _intent_model(state)
    plan = _response_plan(state)

    assert {item["key"] for item in model["explicit_questions"]} >= {
        "can_repair_vehicle",
        "were_photos_sent",
    }
    assert model["dominant_concern"]["key"] == "preserve_claim_while_repairing_vehicle"
    assert plan["response_priority"][:2] == ["vehicle_repair_authorization", "photo_upload_status"]
    assert state.response.index("arreglar el auto") < state.response.index("fotos")


def test_ambiguous_reference_records_missing_information_before_inferring():
    runtime = build_galicia_runtime()

    state = _run(runtime, "intent-ambiguous", "Eso esta bien?")
    model = _intent_model(state)

    assert model["dominant_concern"]["key"] == "ambiguous_reference"
    assert model["missing_information"][0]["key"] == "reference_target"
    assert model["response_objective"]["need_key"] == "understand_user_need"
