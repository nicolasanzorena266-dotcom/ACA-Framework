from zero_cost.execution_plan import ExecutionPlan, ExecutionStep
from zero_cost.flow_router import ExecutionFlow


def test_execution_plan_can_be_built_from_execution_flow():
    flow = ExecutionFlow(
        flow="knowledge_lookup",
        steps=["policy", "tool_lookup", "kernel", "memory", "context", "output"],
        source_action="knowledge_lookup",
        payload={"tool_key": "cleas"},
    )

    plan = ExecutionPlan.from_flow(flow)

    assert plan.flow == "knowledge_lookup"
    assert plan.source_action == "knowledge_lookup"
    assert plan.step_names() == [
        "policy",
        "tool_lookup",
        "kernel",
        "memory",
        "context",
        "output",
    ]
    assert plan.steps[1] == ExecutionStep(name="tool_lookup", payload={"tool_key": "cleas"})


def test_execution_plan_is_serializable():
    plan = ExecutionPlan.from_flow(
        {
            "flow": "safe_escalation",
            "steps": ["policy", "escalation", "memory", "context", "output"],
            "source_action": "safe_escalation",
            "payload": {"reason": "requires_real_claim_data"},
        }
    )

    assert plan.to_dict() == {
        "flow": "safe_escalation",
        "steps": [
            {"name": "policy", "required": True, "payload": {}},
            {"name": "escalation", "required": True, "payload": {"reason": "requires_real_claim_data"}},
            {"name": "memory", "required": True, "payload": {}},
            {"name": "context", "required": True, "payload": {}},
            {"name": "output", "required": True, "payload": {}},
        ],
        "source_action": "safe_escalation",
        "payload": {"reason": "requires_real_claim_data"},
        "reason": "zero_cost_execution_plan",
    }


def test_execution_plan_falls_back_to_output_step_when_flow_has_no_steps():
    plan = ExecutionPlan.from_flow({"flow": "fallback", "source_action": "fallback_response"})

    assert plan.step_names() == ["output"]
