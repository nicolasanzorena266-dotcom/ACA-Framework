from aca_kernel.core.events import Event
from aca_os.conversation_state import (
    ConversationalActType,
    ConversationalStrategyType,
    conversational_goal_contract,
)
from sdk.factory import build_galicia_runtime


def _run(runtime, conversation_id: str, message: str):
    return runtime.process(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))


def _prepare_guided(runtime, conversation_id: str):
    _run(runtime, conversation_id, "Me chocaron ayer")
    _run(runtime, conversation_id, "No")
    _run(runtime, conversation_id, "Soy asegurado.")


def _goal(state):
    return state.facts["conversation_goal"]["goal"]


def _fulfillment(state):
    return state.facts["conversation_goal"]["fulfillment"]


def test_conversational_goal_contract_is_explicit():
    contract = conversational_goal_contract()

    assert contract["contract"] == "conversational_goal.v1"
    assert ConversationalStrategyType.SIMPLIFY in contract["strategies"]
    assert ConversationalStrategyType.SUMMARIZE in contract["strategies"]
    assert "success_criteria" in contract["required_fields"]
    assert "abandonment_criteria" in contract["required_fields"]
    assert "mission_impact" in contract["required_fields"]


def test_simplification_act_generates_goal_strategy_and_satisfied_response():
    runtime = build_galicia_runtime()
    _prepare_guided(runtime, "goal-simple")

    state = _run(runtime, "goal-simple", "Explicamelo mas simple.")
    goal = _goal(state)
    fulfillment = _fulfillment(state)

    assert goal["originating_act"]["act"] == ConversationalActType.SIMPLIFICATION_REQUEST
    assert goal["strategy"]["name"] == ConversationalStrategyType.SIMPLIFY
    assert goal["intention"] == "make_current_guidance_easier_to_understand"
    assert goal["mission_impact"]["preserve_active_mission"] is True
    assert "Mas simple" in state.response
    assert "denuncia ya esta cargada" in state.response
    assert fulfillment["satisfied"] is True
    assert fulfillment["checks"]["simple_marker"] is True


def test_recap_act_generates_real_summary_from_confirmed_facts():
    runtime = build_galicia_runtime()
    _prepare_guided(runtime, "goal-recap")

    state = _run(runtime, "goal-recap", "Resumime.")
    goal = _goal(state)
    fulfillment = _fulfillment(state)

    assert goal["strategy"]["name"] == ConversationalStrategyType.SUMMARIZE
    assert goal["success_criteria"] == [
        "response_contains_summary_marker",
        "response_uses_confirmed_facts_only",
    ]
    assert "Resumen breve" in state.response
    assert "no hubo lesionados" in state.response
    assert "sos asegurado" in state.response
    assert fulfillment["satisfied"] is True
    assert fulfillment["checks"]["uses_confirmed_facts"] is True


def test_deepening_act_adds_detail_without_restarting_mission():
    runtime = build_galicia_runtime()
    _prepare_guided(runtime, "goal-deepen")

    state = _run(runtime, "goal-deepen", "Contame mas.")
    goal = _goal(state)
    fulfillment = _fulfillment(state)

    assert goal["strategy"]["name"] == ConversationalStrategyType.DEEPEN
    assert goal["mission_impact"]["active_mission_type"] == "auto_claim_guidance"
    assert state.intent_match["reason"] == "conversation_act_deepening_request"
    assert "Mas detalle" in state.response
    assert "denuncia" in state.response
    assert fulfillment["satisfied"] is True


def test_topic_shift_goal_recovers_available_focus_without_topic_stack_runtime():
    runtime = build_galicia_runtime()
    _prepare_guided(runtime, "goal-topic")

    state = _run(runtime, "goal-topic", "Volvamos a lo anterior.")
    goal = _goal(state)
    response_plan = goal["strategy"]["response_plan"]

    assert goal["strategy"]["name"] == ConversationalStrategyType.SWITCH_TOPIC
    assert response_plan["available_focus"]["active_mission_type"] == "auto_claim_guidance"
    assert "Retomo la denuncia" in state.response
    assert "denuncia ya esta cargada" in state.response
    assert _fulfillment(state)["satisfied"] is True


def test_continuation_goal_continues_current_next_act():
    runtime = build_galicia_runtime()
    _prepare_guided(runtime, "goal-continue")

    state = _run(runtime, "goal-continue", "Seguimos.")
    goal = _goal(state)

    assert goal["strategy"]["name"] == ConversationalStrategyType.CONTINUE
    assert goal["strategy"]["response_plan"]["mission_next_act"] == "check_claim_report_loaded"
    assert "denuncia ya esta cargada" in state.response
    assert _fulfillment(state)["satisfied"] is True


def test_ambiguous_correction_goal_asks_clarification_and_marks_fulfillment():
    runtime = build_galicia_runtime()
    _run(runtime, "goal-clarify", "Me chocaron ayer")
    _run(runtime, "goal-clarify", "No hubo lesionados y soy asegurado.")

    state = _run(runtime, "goal-clarify", "Me confundi.")
    goal = _goal(state)

    assert goal["strategy"]["name"] == ConversationalStrategyType.ASK_CLARIFICATION
    assert goal["mission_impact"]["preserve_active_mission"] is True
    assert "lesionados, rol, denuncia o documentacion" in state.response
    assert _fulfillment(state)["satisfied"] is True


def test_closing_goal_produces_close_strategy_instead_of_fallback():
    runtime = build_galicia_runtime()
    _prepare_guided(runtime, "goal-close")

    state = _run(runtime, "goal-close", "Gracias.")
    goal = _goal(state)

    assert goal["strategy"]["name"] == ConversationalStrategyType.CLOSE
    assert "pausada" in state.response
    assert _fulfillment(state)["satisfied"] is True
