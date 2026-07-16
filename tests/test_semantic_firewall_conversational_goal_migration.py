from pathlib import Path

from aca_kernel.core.events import Event
from aca_os.authority_dependency_graph import build_authority_dependency_graph
from aca_os.conversation_manager import ConversationManager
from sdk.factory import build_galicia_runtime


ROOT = Path(__file__).resolve().parents[1]


def _event(message: str, conversation_id: str) -> Event:
    return Event(
        type="user_message",
        payload=message,
        metadata={"conversation_id": conversation_id},
    )


class _FailingSemanticAuthority:
    def interpret(self, *args, **kwargs):
        raise RuntimeError("semantic goal test failure")


def test_fw5_removes_the_conversational_goal_text_violation():
    graph = build_authority_dependency_graph(ROOT)
    goal_accesses = [
        item
        for item in graph.semantic_firewall_audit
        if item["artifact"] == "conversational_goal"
    ]

    assert goal_accesses == []
    # FW-11 resolved the 4 duplicate pre-Mission planning writes, dropping
    # the violation count from 30 to 26.
    assert graph.report["summary"]["semantic_firewall_violation_count"] == 26


def test_conversational_goal_selects_one_complete_semantic_candidate():
    manager = ConversationManager(semantic_authority_pilot_enabled=True)
    turn = manager.begin_turn(_event("Hola", "fw5-semantic"))
    decision = turn.conversational_goal_authority

    assert decision["authority_mode"] == "semantic"
    assert decision["authority_selected"] == "semantic"
    assert decision["selected_value"] == decision["semantic_value"]
    assert decision["agreement"] is True
    assert decision["state_delta_parity"] is True
    assert decision["atomic_selection"] is True
    assert decision["mixed_authority"] is False
    assert decision["downstream_text_access"] is False
    assert decision["firewall_package"] == "FW-5"
    assert turn.conversational_goal == decision["selected_value"]
    assert "message" not in turn.conversational_goal["evidence"]
    assert (
        turn.conversational_goal["evidence"]["semantic_goal"]["target"]
        == "greet"
    )


def test_conversational_goal_rolls_back_atomically_when_semantics_fail():
    manager = ConversationManager(
        semantic_authority=_FailingSemanticAuthority(),
        semantic_authority_pilot_enabled=True,
    )
    turn = manager.begin_turn(_event("Me chocaron ayer", "fw5-rollback"))
    decision = turn.conversational_goal_authority

    assert decision["authority_mode"] == "rollback"
    assert decision["authority_selected"] == "legacy"
    assert decision["rollback_reason"] == "semantic_pipeline_exception"
    assert decision["selected_value"] == decision["legacy_value"]
    assert decision["selected_value_hash"] == decision["legacy_value_hash"]
    assert decision["mixed_authority"] is False
    assert turn.conversational_goal == decision["legacy_value"]
    assert "message" not in turn.conversational_goal["evidence"]


def test_goal_authority_telemetry_is_exposed_in_runtime_trace(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    runtime = build_galicia_runtime()
    state = runtime.process(_event("Hola", "fw5-trace"))
    record = state.facts["conversation_state_runtime"]
    trace = runtime.export_trace()
    authority = record["conversational_goal_authority"]
    metrics = record["conversational_goal_authority_metrics"]
    event = next(
        item
        for item in trace["events"]
        if item["operation"] == "SEMANTIC_FIREWALL_CONVERSATIONAL_GOAL"
    )

    assert authority["authority_selected"] == "semantic"
    assert metrics["semantic_usage"] == {"count": 1, "rate": 1.0}
    assert metrics["legacy_usage"] == {"count": 0, "rate": 0.0}
    assert metrics["rollback_rate"] == 0.0
    assert metrics["agreement_rate"] == 1.0
    assert metrics["atomic_selection_violations"] == 0
    assert event["metadata"]["firewall_package"] == "FW-5"
    assert event["metadata"]["downstream_text_access"] is False
    assert trace["conversational_goal_authority"]["consumer"] == (
        "conversational_goal"
    )


def test_visible_response_and_execution_plan_are_stable_across_goal_rollback(
    monkeypatch,
):
    monkeypatch.setenv("LLM_ENABLED", "false")
    semantic_runtime = build_galicia_runtime()
    semantic = semantic_runtime.process(
        _event("Me chocaron ayer", "fw5-visible-semantic")
    )

    legacy_runtime = build_galicia_runtime()
    legacy_runtime.conversation_manager = ConversationManager(
        semantic_authority=_FailingSemanticAuthority(),
        semantic_authority_pilot_enabled=True,
    )
    legacy = legacy_runtime.process(_event("Me chocaron ayer", "fw5-visible-legacy"))

    assert semantic.response == legacy.response
    assert semantic.intent_match == legacy.intent_match
    assert semantic.facts["zero_cost_action_plan"] == legacy.facts[
        "zero_cost_action_plan"
    ]
    assert semantic.facts["zero_cost_execution_flow"] == legacy.facts[
        "zero_cost_execution_flow"
    ]
    assert semantic.facts["zero_cost_execution_plan"] == legacy.facts[
        "zero_cost_execution_plan"
    ]


def test_official_goal_call_no_longer_receives_event_payload():
    source = (ROOT / "aca_os" / "conversation_manager.py").read_text(
        encoding="utf-8"
    )

    assert "apply_conversational_goal(event.payload)" not in source
    assert "project_conversational_goal(" in source
