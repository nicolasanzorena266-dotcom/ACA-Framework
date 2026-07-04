from zero_cost.action_planner import ActionPlan
from zero_cost.flow_router import ExecutionFlow, FlowRouter


def test_routes_knowledge_lookup_action_to_knowledge_flow():
    router = FlowRouter()
    flow = router.route(
        ActionPlan(
            action="knowledge_lookup",
            confidence=1.0,
            source_intent="concept_cleas",
            payload={"tool_key": "cleas"},
        )
    )

    assert isinstance(flow, ExecutionFlow)
    assert flow.flow == "knowledge_lookup"
    assert flow.source_action == "knowledge_lookup"
    assert flow.payload["tool_key"] == "cleas"
    assert flow.steps == ["policy", "tool_lookup", "kernel", "memory", "context", "output"]


def test_routes_human_handoff_action_to_handoff_flow():
    router = FlowRouter()
    flow = router.route(
        {
            "action": "human_handoff",
            "confidence": 0.5,
            "source_intent": "human_request",
            "payload": {"reason": "explicit_human_request"},
        }
    )

    assert flow.flow == "human_handoff"
    assert "handoff" in flow.steps
    assert flow.payload["reason"] == "explicit_human_request"


def test_unknown_action_routes_to_fallback_flow():
    router = FlowRouter()
    flow = router.route({"action": "unknown_action"})

    assert flow.flow == "fallback"
    assert flow.source_action == "unknown_action"
    assert flow.reason == "no_flow_route_matched"
