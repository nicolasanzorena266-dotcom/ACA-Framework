from zero_cost.action_planner import ActionPlanner
from zero_cost.intent_matcher import IntentMatcher


def test_action_planner_maps_concept_to_knowledge_lookup():
    intent_match = IntentMatcher().match("Que es CLEAS?")

    plan = ActionPlanner().plan(intent_match)

    assert plan.action == "knowledge_lookup"
    assert plan.source_intent == "concept_cleas"
    assert plan.payload["tool_key"] == "cleas"


def test_action_planner_maps_real_claim_status_to_safe_escalation():
    intent_match = IntentMatcher().match("Cuando me pagan?")

    plan = ActionPlanner().plan(intent_match)

    assert plan.action == "safe_escalation"
    assert plan.payload["reason"] == "requires_real_claim_data"


def test_action_planner_fallback_for_unknown_intent():
    plan = ActionPlanner().plan({"intent": "unknown", "confidence": 0.7})

    assert plan.action == "fallback_response"
    assert plan.reason == "no_action_rule_matched"


def test_action_planner_can_request_clarification_below_threshold():
    planner = ActionPlanner(
        {
            "weak_intent": {
                "action": "some_action",
                "min_confidence": 0.8,
            }
        }
    )

    plan = planner.plan({"intent": "weak_intent", "confidence": 0.3})

    assert plan.action == "clarify"
    assert plan.reason == "below_min_confidence"
