from aca_kernel.core.events import Event
from aca_os.conversation_state import ConversationState, information_gain_plan_contract
from sdk.factory import build_galicia_runtime


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _information_gain_plan(state):
    return state.facts["conversation_information_gain_plan"]["plan"]


def _response_plan(state):
    return state.facts["conversation_response_plan"]["plan"]


def test_information_gain_plan_contract_is_explicit():
    contract = information_gain_plan_contract()

    assert contract["contract"] == "information_gain_plan.v1"
    assert contract["required_fields"] == [
        "candidate_questions",
        "expected_information_gain",
        "affected_decisions",
        "estimated_cost",
        "blocking_level",
        "clarification_priority",
        "selected_question",
    ]
    assert contract["turn_scoped_projection"] == "conversation_information_gain_plan"


def test_five_missing_items_select_question_with_highest_decision_value():
    state = ConversationState(
        conversation_id="ig-five",
        turn_count=1,
        active_mission={"type": "auto_claim_guidance", "next_act": "ask_injuries"},
        pending_questions=[
            {"slot": "injuries", "priority": 10, "source": "test"},
            {"slot": "user_role", "priority": 20, "source": "test"},
            {"slot": "claim_report_loaded", "priority": 30, "source": "test"},
            {"slot": "documentation_available", "priority": 35, "source": "test"},
            {"slot": "damage_evidence_available", "priority": 40, "source": "test"},
        ],
    )

    state, _ = state.model_conversational_intent("Me chocaron.")
    _, plan = state.plan_information_gain("Me chocaron.")

    assert len(plan["candidate_questions"]) == 5
    assert plan["selected_question"]["slot"] == "injuries"
    assert plan["affected_decisions"] == ["safety_and_escalation_path"]
    assert plan["question_count_metric"]["avoided_question_count"] == 4


def test_runtime_asks_only_selected_clarification_for_auto_claim_start():
    runtime = build_galicia_runtime()

    state = _run(runtime, "ig-runtime-selected", "Me chocaron ayer")
    information_gain = _information_gain_plan(state)
    response_plan = _response_plan(state)

    assert information_gain["selected_question"]["slot"] == "injuries"
    assert information_gain["question_count_metric"]["candidate_question_count"] >= 2
    assert information_gain["question_count_metric"]["avoided_question_count"] >= 1
    assert [item["slot"] for item in response_plan["required_information"]] == ["injuries"]
    assert "Hubo lesionados?" in state.response
    assert "Sos asegurado" not in state.response


def test_can_answer_process_progress_without_immediate_low_value_question():
    runtime = build_galicia_runtime()

    state = _run(runtime, "ig-contact", "Cuando me van a contactar?")
    information_gain = _information_gain_plan(state)
    response_plan = _response_plan(state)

    assert information_gain["candidate_questions"]
    assert information_gain["selected_question"] == {}
    assert information_gain["can_continue_without_question"] is True
    assert response_plan["required_information"] == []
    assert "siguiendo el circuito esperado" in state.response
    assert "La denuncia ya esta cargada?" not in state.response


def test_no_question_when_missing_information_does_not_change_current_decision():
    runtime = build_galicia_runtime()

    state = _run(runtime, "ig-no-question", "No me pidieron las fotos.")
    information_gain = _information_gain_plan(state)
    response_plan = _response_plan(state)

    assert {item["slot"] for item in information_gain["candidate_questions"]} >= {"claim_type", "channel_checklist"}
    assert information_gain["selected_question"] == {}
    assert response_plan["required_information"] == []
    assert "Que tipo de siniestro fue?" not in state.response
    assert "canal te muestra" not in state.response


def test_similar_utility_questions_record_deterministic_tie_break():
    state = ConversationState(
        conversation_id="ig-tie",
        turn_count=1,
        active_mission={"type": "auto_claim_guidance", "next_act": "check_claim_report_loaded"},
        pending_questions=[
            {"slot": "claim_report_loaded", "priority": 30, "source": "test"},
            {"slot": "documentation_available", "priority": 30, "source": "test"},
        ],
    )

    state, _ = state.model_conversational_intent("Seguimos con el tramite.")
    _, plan = state.plan_information_gain("Seguimos con el tramite.")

    assert plan["selected_question"]["slot"] == "claim_report_loaded"
    assert plan["selection_reason"] == "highest_information_gain_with_deterministic_tie_break"
    assert plan["tie_break"]["candidate_slots"] == ["claim_report_loaded", "documentation_available"]
