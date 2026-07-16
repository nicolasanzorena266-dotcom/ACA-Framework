from aca_kernel.core.events import Event
from aca_os.conversation_manager import ConversationManager
from aca_os.semantic_authority_pilot import (
    select_conversational_act_authority,
)
from sdk.factory import build_galicia_runtime


def _event(message: str, conversation_id: str) -> Event:
    return Event(
        type="user_message",
        payload=message,
        metadata={"conversation_id": conversation_id},
    )


def test_greeting_promotes_only_the_complete_semantic_conversational_act():
    manager = ConversationManager(semantic_authority_pilot_enabled=True)
    turn = manager.begin_turn(_event("Hola", "sa3-semantic"))
    decision = turn.semantic_authority_pilot

    assert decision["consumer"] == "conversational_act"
    assert decision["authority_mode"] == "semantic"
    assert decision["authority_selected"] == "semantic"
    assert decision["authority_reason"] == "low_risk_semantic_act_promoted"
    assert decision["legacy_value"]["act"] == "new_information"
    assert decision["semantic_value"]["act"] == "greeting"
    assert decision["selected_value"] == decision["semantic_value"]
    assert decision["selected_value_hash"] == decision["semantic_value_hash"]
    assert decision["atomic_selection"] is True
    assert decision["mixed_authority"] is False
    assert turn.conversational_act == decision["semantic_value"]
    assert turn.conversation_state.last_conversational_act == decision["semantic_value"]
    assert (
        turn.conversation_state.derived_state["conversation_act"]["component"]
        == "semantic_projector"
    )
    assert "semantic_authority.conversational_act" in turn.conversation_state.projection_sources
    assert "conversation_state.conversational_act_recognition" not in (
        turn.conversation_state.projection_sources
    )


def test_out_of_scope_turn_rolls_back_atomically_to_legacy():
    manager = ConversationManager(semantic_authority_pilot_enabled=True)
    turn = manager.begin_turn(_event("No hubo heridos.", "sa3-rollback"))
    decision = turn.semantic_authority_pilot

    assert decision["authority_mode"] == "rollback"
    assert decision["authority_selected"] == "legacy"
    assert decision["rollback_reason"] == "confidence_below_threshold"
    assert decision["selected_value"] == decision["legacy_value"]
    assert decision["selected_value_hash"] == decision["legacy_value_hash"]
    assert turn.conversational_act == decision["legacy_value"]
    assert turn.conversation_state.last_conversational_act == decision["legacy_value"]
    assert decision["mixed_authority"] is False


def test_critical_semantic_risk_forces_rollback():
    manager = ConversationManager(semantic_authority_pilot_enabled=True)
    turn = manager.begin_turn(_event("Eso.", "sa3-critical"))
    decision = turn.semantic_authority_pilot

    assert decision["authority_mode"] == "rollback"
    assert decision["authority_reason"] == "critical_semantic_risk"
    assert "unresolved_coreference" in decision["critical_errors"]
    assert decision["selected_value"] == decision["legacy_value"]


def test_pilot_can_be_disabled_without_affecting_legacy():
    manager = ConversationManager(semantic_authority_pilot_enabled=False)
    turn = manager.begin_turn(_event("Hola", "sa3-disabled"))
    decision = turn.semantic_authority_pilot

    assert decision["authority_mode"] == "legacy"
    assert decision["authority_selected"] == "legacy"
    assert decision["authority_reason"] == "pilot_disabled"
    assert decision["rollback_reason"] == ""
    assert turn.conversational_act["act"] == "new_information"


class _FailingSemanticAuthority:
    def interpret(self, *args, **kwargs):
        raise RuntimeError("semantic test failure")


def test_semantic_exception_rolls_back_without_interrupting_the_turn():
    manager = ConversationManager(
        semantic_authority=_FailingSemanticAuthority(),
        semantic_authority_pilot_enabled=True,
    )
    turn = manager.begin_turn(_event("Hola", "sa3-exception"))
    decision = turn.semantic_authority_pilot
    record = manager.conversation_state_runtime_record("sa3-exception")

    assert decision["authority_mode"] == "rollback"
    assert decision["rollback_reason"] == "semantic_pipeline_exception"
    assert decision["selected_value"] == decision["legacy_value"]
    assert turn.conversational_act["act"] == "new_information"
    assert record["semantic_failure"]["type"] == "RuntimeError"
    assert record["semantic_projection_shadow"]["available"] is False


def test_invalid_projection_is_rejected_by_the_atomic_selector():
    decision = select_conversational_act_authority(
        legacy_act={"contract": "conversational_act.v1", "act": "new_information"},
        semantic_projection={"conversation_intent_model": {}},
        semantic_representation={"grounding": {}, "topic_structure": {}},
        enabled=True,
    )

    assert decision["authority_mode"] == "rollback"
    assert decision["rollback_reason"] == "invalid_semantic_projection"
    assert decision["projection_valid"] is False
    assert decision["selected_value"] == decision["legacy_value"]


def test_pilot_metrics_cover_promotion_rollback_usage_and_failures():
    manager = ConversationManager(semantic_authority_pilot_enabled=True)
    first = manager.begin_turn(_event("Hola", "sa3-metrics"))
    manager.begin_turn(_event("No hubo heridos.", "sa3-metrics"), first.cognitive_state)
    metrics = manager.conversation_state_runtime_record("sa3-metrics")[
        "semantic_authority_pilot_metrics"
    ]

    assert metrics["turn_count"] == 2
    assert metrics["promotion_count"] == 1
    assert metrics["rollback_count"] == 1
    assert metrics["promotion_rate"] == 0.5
    assert metrics["rollback_rate"] == 0.5
    assert metrics["semantic_authority_usage"] == {"count": 1, "rate": 0.5}
    assert metrics["legacy_usage"] == {"count": 1, "rate": 0.5}
    assert metrics["failure_distribution"] == {"confidence_below_threshold": 1}
    assert metrics["atomic_selection_violations"] == 0


def test_runtime_visible_response_and_core_pipeline_are_stable(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("SEMANTIC_AUTHORITY_PILOT_ENABLED", "false")
    legacy_runtime = build_galicia_runtime()
    legacy = legacy_runtime.process(_event("Hola", "sa3-visible-legacy"))

    monkeypatch.setenv("SEMANTIC_AUTHORITY_PILOT_ENABLED", "true")
    semantic_runtime = build_galicia_runtime()
    semantic = semantic_runtime.process(_event("Hola", "sa3-visible-semantic"))
    record = semantic.facts["conversation_state_runtime"]
    trace = semantic_runtime.export_trace()

    assert semantic.response == legacy.response
    assert semantic.intent_match == legacy.intent_match
    assert semantic.facts["zero_cost_action_plan"] == legacy.facts["zero_cost_action_plan"]
    assert semantic.facts["zero_cost_execution_flow"] == legacy.facts["zero_cost_execution_flow"]
    assert semantic.facts["zero_cost_execution_plan"] == legacy.facts["zero_cost_execution_plan"]
    assert record["semantic_authority_pilot"]["authority_mode"] == "semantic"
    assert record["conversation_act"]["selected"]["act"] == "greeting"
    assert (
        record["semantic_projection_shadow"]["legacy_projection"]["conversational_act"]["act"]
        == "new_information"
    )
    assert "SEMANTIC_AUTHORITY_VERTICAL_PILOT" in trace["operations"]
    assert trace["semantic_authority_pilot"]["authority_selected"] == "semantic"
    pilot_event = next(
        item
        for item in trace["events"]
        if item["operation"] == "SEMANTIC_AUTHORITY_VERTICAL_PILOT"
    )
    assert pilot_event["output"]["selected_value"]["act"] == "greeting"
    assert pilot_event["metadata"]["atomic_selection"] is True
    assert pilot_event["metadata"]["mixed_authority"] is False
