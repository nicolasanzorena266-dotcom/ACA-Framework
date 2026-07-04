from aca_kernel.core.events import Event
from sdk.factory import build_galicia_runtime


def test_runtime_persists_zero_cost_execution_plan():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="Que es CLEAS?"))

    plan = state.facts["zero_cost_execution_plan"]
    assert plan["flow"] == "knowledge_lookup"
    assert [step["name"] for step in plan["steps"]] == [
        "policy",
        "tool_lookup",
        "kernel",
        "memory",
        "context",
        "output",
    ]
    assert plan["steps"][1]["payload"] == {"tool_key": "cleas"}


def test_runtime_timeline_includes_execution_plan_operation():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="quiero hablar con un asesor"))

    operations = [entry["operation"] for entry in state.timeline]
    assert "INTENT_MATCH" in operations
    assert "ACTION_PLAN" in operations
    assert "FLOW_ROUTE" in operations
    assert "EXECUTION_PLAN" in operations
