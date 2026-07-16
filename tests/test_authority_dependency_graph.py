import json

import pytest

from aca_kernel.core.events import Event
from aca_os.authority_dependency_graph import build_authority_dependency_graph
from aca_os.introspection import RuntimeIntrospectionAPI
from sdk.factory import build_galicia_runtime


def _node(graph, artifact):
    return next(item for item in graph.nodes if item["id"] == artifact)


def _readiness(graph, artifact):
    return next(item for item in graph.promotion_readiness if item["artifact"] == artifact)


def test_graph_is_reproducible_and_every_edge_has_source_evidence():
    first = build_authority_dependency_graph()
    second = build_authority_dependency_graph()

    assert first.graph_hash == second.graph_hash
    assert first.source_hash == second.source_hash
    assert len(first.nodes) >= 30
    assert len(first.edges) >= 25
    assert all(edge["evidence"] for edge in first.edges)
    assert json.loads(json.dumps(first.to_dict()))["contract"] == "authority_dependency_graph.v1"


def test_semantic_firewall_finds_runtime_reinterpretation_with_exact_locations():
    graph = build_authority_dependency_graph()
    violations = [
        item
        for item in graph.semantic_firewall_audit
        if item["classification"] == "SEMANTIC_FIREWALL_VIOLATION"
    ]

    assert any(
        item["file"] == "aca_os/runtime.py"
        and item["function"] == "ACAOSRuntime.process"
        and item["artifact"] == "intent_match"
        for item in violations
    )
    assert any(
        item["file"] == "aca_os/mission_manager.py"
        and item["artifact"] == "mission"
        for item in violations
    )
    assert all(item["line"] > 0 for item in violations)
    assert all(item["purpose"] and item["impact"] for item in violations)


@pytest.mark.parametrize(
    "artifact",
    [
        "conversation_intent_model",
        "information_gain_plan",
        "conversation_plan",
        "conversation_response_plan",
    ],
)
def test_post_mission_plans_are_no_longer_recomputed_after_fw11(artifact):
    """FW-11 resolved: each of these artifacts now has exactly one writer.

    ConversationManager.begin_turn used to compute these before MissionManager
    even ran; that premature write was removed because nothing consumed it
    (verified by instrumentation, see aca_os/fw11_recomputation_evidence.py)
    and it was always overwritten by ACAOSRuntime.process's post-Mission
    write. Only that single write remains.
    """
    graph = build_authority_dependency_graph()
    overwritten = [
        item
        for item in graph.recomputation_audit
        if item["artifact"] == artifact and item["type"] == "RECOMPUTED_AND_OVERWRITTEN"
    ]

    assert overwritten == []
    assert _readiness(graph, artifact)["recomputed"] is False


def test_promotion_order_is_code_derived_and_blocks_false_intent_promotion():
    graph = build_authority_dependency_graph()

    # ACA-303 gave ConversationalGoal's atomic selector (select_conversational_
    # goal_authority) the same GUARDED_MULTI_AUTHORITY/READY treatment already
    # applied to ConversationalAct, closing the static-vs-real authority gap
    # ACA-200 flagged. Both are now READY; ConversationalGoal sorts first
    # because it has lower producer/consumer coupling (2 vs 3).
    assert graph.promotion_order[0]["artifact"] == "conversational_goal"
    assert graph.promotion_order[0]["readiness"] == "READY"
    assert graph.promotion_order[1]["artifact"] == "conversational_act"
    assert graph.promotion_order[1]["readiness"] == "READY"
    assert _readiness(graph, "conversational_goal")["status"] == "READY"
    assert _readiness(graph, "conversational_goal")["reason"] == (
        "Already promoted only when projection validity, confidence, "
        "decision agreement and state-effect parity all pass, with atomic "
        "Legacy rollback."
    )
    # FW-11 resolved the duplicate writer: conversation_intent_model is no
    # longer BLOCKED by recomputation. It remains HIGH_RISK because it still
    # has critical free-text dependencies -- a separate, still-open FW-10
    # concern, not FW-11.
    assert _readiness(graph, "conversation_intent_model")["status"] == "HIGH_RISK"
    assert _readiness(graph, "conversation_intent_model")["recomputed"] is False
    assert _readiness(graph, "policy_result")["status"] == "BLOCKED"
    assert "independent" in _readiness(graph, "policy_result")["reason"].lower()


def test_authority_scores_cycles_and_atomic_pilot_are_visible():
    graph = build_authority_dependency_graph()
    act = _node(graph, "conversational_act")

    assert pytest.approx(sum(act["authority_score"].values()), abs=0.0001) == 1.0
    assert act["effective_authority"] == "semantic_pilot_for_greeting_else_legacy"
    assert "PRIMARY_AUTHORITY" in act["classifications"]
    assert "RECOMPUTED" in act["classifications"]
    assert any(
        item["artifact"] == "conversational_act"
        and item["type"] == "GUARDED_MULTI_AUTHORITY"
        for item in graph.recomputation_audit
    )
    assert graph.dependency_cycles


def test_mermaid_visualization_marks_readiness_without_changing_runtime():
    graph = build_authority_dependency_graph()
    mermaid = graph.to_mermaid()

    assert mermaid.startswith("flowchart TD")
    assert "SemanticRepresentation" in mermaid
    assert "ConversationIntentModel" in mermaid
    # ConversationalAct and ConversationalGoal are both READY (ACA-303) and
    # are grouped in the same mermaid class line.
    assert "class N_conversational_act,N_conversational_goal ready" in mermaid
    assert "classDef blocked" in mermaid


def test_runtime_introspection_overlays_existing_trace_and_preserves_response(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "false")
    runtime = build_galicia_runtime()
    state = runtime.process(
        Event(
            type="user_message",
            payload="Hola",
            metadata={"conversation_id": "authority-graph"},
        )
    )
    response_before = state.response

    introspection = RuntimeIntrospectionAPI(runtime)
    graph = introspection.inspect_authority_graph()
    artifact = introspection.inspect_authority_graph("conversation_intent_model")

    assert state.response == response_before == "Hola. Contame qué necesitás y te oriento."
    assert graph["runtime_observation"]["trace_available"] is True
    assert "semantic_representation" in graph["runtime_observation"]["observed_artifacts"]
    assert "conversational_act" in graph["runtime_observation"]["observed_artifacts"]
    assert artifact["artifact"]["id"] == "conversation_intent_model"
    # FW-11 resolved: there is no longer a second writer to recompute.
    assert artifact["recomputations"] == []
    # A separate, still-open (FW-10-scoped) free-text read remains.
    assert artifact["semantic_firewall_violations"]
