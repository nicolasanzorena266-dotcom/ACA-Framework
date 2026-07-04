from zero_cost.action_planner import ActionPlan
from zero_cost.decision_graph import DecisionGraphEngine
from zero_cost.execution_plan import ExecutionPlan
from zero_cost.flow_router import ExecutionFlow
from zero_cost.intent_matcher import IntentMatch


def test_decision_graph_engine_builds_selected_runtime_path():
    graph = DecisionGraphEngine().build(
        intent_match=IntentMatch(intent="concept_cleas", confidence=1.0, matched_terms=["cleas"]),
        action_plan=ActionPlan(
            action="knowledge_lookup",
            confidence=1.0,
            source_intent="concept_cleas",
            payload={"tool_key": "cleas"},
        ),
        execution_flow=ExecutionFlow(
            flow="knowledge_lookup",
            steps=["policy", "tool_lookup", "kernel", "memory", "context", "output"],
            source_action="knowledge_lookup",
            payload={"tool_key": "cleas"},
        ),
        execution_plan=ExecutionPlan.from_flow(
            {
                "flow": "knowledge_lookup",
                "steps": ["policy", "tool_lookup", "kernel", "memory", "context", "output"],
                "source_action": "knowledge_lookup",
                "payload": {"tool_key": "cleas"},
            }
        ),
    )

    assert graph.graph_id == "runtime.decision_graph.v1"
    assert graph.node_ids() == [
        "input.intent",
        "plan.action",
        "route.flow",
        "execution.plan",
    ]
    assert graph.selected_path == graph.node_ids()
    assert graph.terminal_node == "execution.plan"
    assert [edge.reason for edge in graph.edges] == [
        "intent_to_action",
        "action_to_flow",
        "flow_to_execution_plan",
    ]


def test_decision_graph_is_serializable():
    graph = DecisionGraphEngine().build(
        intent_match={"intent": "fallback", "confidence": 0.0, "matched_terms": [], "reason": "no_rule_matched"},
        action_plan={"action": "fallback_response", "confidence": 0.0, "source_intent": "fallback"},
        execution_flow={"flow": "fallback", "steps": ["kernel", "memory", "context", "output"]},
        execution_plan={"flow": "fallback", "steps": [{"name": "output", "required": True, "payload": {}}]},
    )

    data = graph.to_dict()

    assert data["reason"] == "zero_cost_decision_graph"
    assert data["nodes"][0]["kind"] == "intent"
    assert data["nodes"][1]["kind"] == "action"
    assert data["nodes"][2]["kind"] == "flow"
    assert data["nodes"][3]["kind"] == "execution_plan"
