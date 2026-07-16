from pathlib import Path

from aca_kernel.core.events import Event
from aca_os.authority_dependency_graph import build_authority_dependency_graph
from aca_os.conversation_manager import ConversationManager
from aca_os.semantic_firewall_plan import (
    build_semantic_firewall_refactoring_plan,
    select_first_eligible_migration_package,
)
from sdk.factory import build_galicia_runtime


ROOT = Path(__file__).resolve().parents[1]
PROHIBITED_COMPONENTS = (
    "runtime_executor",
    "conversation_state",
    "semantic_authority",
    "mission_manager",
    "operational_work_mapper",
    "action_planner",
    "flow_router",
    "kernel",
    "narrative_response_composer",
    "llm_verbalizer",
    "policy_manager",
    "governance",
    "ledger",
)


def _event(message: str, conversation_id: str) -> Event:
    return Event(
        type="user_message",
        payload=message,
        metadata={"conversation_id": conversation_id},
    )


def test_masterplan_selects_fw4_after_excluding_non_migration_and_prohibited_packages():
    plan = build_semantic_firewall_refactoring_plan(ROOT)
    selection = select_first_eligible_migration_package(
        plan,
        prohibited_components=PROHIBITED_COMPONENTS,
    )

    assert selection["selected"]["package_id"] == "FW-4"
    assert selection["selected"]["name"] == "ConversationalAct Legacy retirement"
    assert selection["selected"]["readiness"] == "READY"
    assert selection["selected"]["forecast_status"] == "FULL_PROMOTION_ELIGIBLE"
    assert selection["document_name"] == (
        "ACA-101_FW2_ConversationalAct_Legacy_retirement.md"
    )
    reasons = {
        item["package_id"]: item["selection_reason"]
        for item in selection["evaluated_before_selection"]
    }
    assert reasons == {
        "FW-A0": "allowlist_baseline_not_a_migration",
        "FW-2": "component_prohibited_by_rc",
        "FW-3": "component_prohibited_by_rc",
        "FW-4": "selected",
    }


def test_legacy_act_capture_is_before_semantic_firewall_in_source_order():
    source = (ROOT / "aca_os" / "conversation_manager.py").read_text(encoding="utf-8")

    legacy_index = source.index("initial.recognize_conversational_act(")
    semantic_index = source.index("self.semantic_authority.interpret(")

    assert legacy_index < semantic_index


def test_authority_graph_has_no_downstream_conversational_act_text_violation():
    graph = build_authority_dependency_graph(ROOT)
    act_accesses = [
        item
        for item in graph.semantic_firewall_audit
        if item["artifact"] == "conversational_act"
    ]

    assert len(act_accesses) == 2
    assert all(
        item["classification"] == "LEGACY_PREFIREWALL_COMPARISON_ACCESS"
        for item in act_accesses
    )
    assert all(item["phase"] == "pre_semantic_compatibility" for item in act_accesses)
    assert not any(
        item["classification"] == "SEMANTIC_FIREWALL_VIOLATION"
        for item in act_accesses
    )
    # FW-11 resolved the 4 duplicate pre-Mission planning writes, dropping
    # the violation count from 30 to 26.
    assert graph.report["summary"]["semantic_firewall_violation_count"] == 26


def test_semantic_selection_keeps_complete_legacy_comparison_and_firewall_metadata():
    manager = ConversationManager(semantic_authority_pilot_enabled=True)
    turn = manager.begin_turn(_event("Hola", "fw2-semantic"))
    decision = turn.semantic_authority_pilot

    assert decision["authority_selected"] == "semantic"
    assert decision["selected_value"] == decision["semantic_value"]
    assert decision["legacy_value"]["act"] == "new_information"
    assert decision["semantic_value"]["act"] == "greeting"
    assert decision["field_diff"]
    assert decision["firewall_package"] == "FW-4"
    assert decision["legacy_capture_phase"] == "pre_semantic_compatibility"
    assert decision["downstream_text_access"] is False
    assert decision["mixed_authority"] is False


def test_rollback_uses_complete_pre_firewall_legacy_candidate():
    manager = ConversationManager(semantic_authority_pilot_enabled=True)
    turn = manager.begin_turn(_event("No hubo heridos.", "fw2-rollback"))
    decision = turn.semantic_authority_pilot

    assert decision["authority_mode"] == "rollback"
    assert decision["authority_selected"] == "legacy"
    assert decision["selected_value"] == decision["legacy_value"]
    assert decision["selected_value_hash"] == decision["legacy_value_hash"]
    assert decision["legacy_capture_phase"] == "pre_semantic_compatibility"
    assert decision["downstream_text_access"] is False
    assert decision["mixed_authority"] is False


def test_trace_and_session_metrics_expose_fw4_without_new_authority(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    runtime = build_galicia_runtime()
    state = runtime.process(_event("Hola", "fw2-trace"))
    trace = runtime.export_trace()
    record = state.facts["conversation_state_runtime"]
    pilot_event = next(
        item
        for item in trace["events"]
        if item["operation"] == "SEMANTIC_AUTHORITY_VERTICAL_PILOT"
    )

    assert pilot_event["metadata"]["firewall_package"] == "FW-4"
    assert pilot_event["metadata"]["legacy_capture_phase"] == (
        "pre_semantic_compatibility"
    )
    assert pilot_event["metadata"]["downstream_text_access"] is False
    assert record["semantic_authority_pilot_metrics"]["firewall_compliant_turns"] == 1
    assert trace["semantic_authority_pilot"]["mixed_authority"] is False


def test_visible_response_and_downstream_plan_remain_equal_with_process_rollback(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("SEMANTIC_AUTHORITY_PILOT_ENABLED", "false")
    legacy_runtime = build_galicia_runtime()
    legacy = legacy_runtime.process(_event("Hola", "fw2-visible-legacy"))

    monkeypatch.setenv("SEMANTIC_AUTHORITY_PILOT_ENABLED", "true")
    semantic_runtime = build_galicia_runtime()
    semantic = semantic_runtime.process(_event("Hola", "fw2-visible-semantic"))

    assert semantic.response == legacy.response
    assert semantic.intent_match == legacy.intent_match
    assert semantic.facts["zero_cost_action_plan"] == legacy.facts["zero_cost_action_plan"]
    assert semantic.facts["zero_cost_execution_flow"] == legacy.facts[
        "zero_cost_execution_flow"
    ]
    assert semantic.facts["zero_cost_execution_plan"] == legacy.facts[
        "zero_cost_execution_plan"
    ]


def test_only_fw4_firewall_accesses_changed_classification():
    plan = build_semantic_firewall_refactoring_plan(ROOT)
    compatibility = [
        item
        for item in plan.inventory
        if item["classification"] == "LEGACY_PREFIREWALL_COMPARISON_ACCESS"
    ]

    assert len(compatibility) == 2
    assert {item["migration_package"] for item in compatibility} == {"FW-4"}
    assert {item["artifact"] for item in compatibility} == {"conversational_act"}
    assert all(
        item["replacement_status"] == "MIGRATED_OUT_OF_DOWNSTREAM_FIREWALL"
        for item in compatibility
    )
    # FW-11 resolved the 4 duplicate pre-Mission planning writes, dropping
    # the violation count from 30 to 26.
    assert plan.summary["violation_count"] == 26
    assert plan.summary["legacy_prefirewall_compatibility_count"] == 2
