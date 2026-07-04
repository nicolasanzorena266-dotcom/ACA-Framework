from aca_kernel.core.events import Event
from sdk.factory import build_galicia_runtime


def test_runtime_persists_zero_cost_decision_graph():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="Que es CLEAS?"))

    graph = state.facts["zero_cost_decision_graph"]
    assert graph["graph_id"] == "runtime.decision_graph.v1"
    assert graph["selected_path"] == [
        "input.intent",
        "plan.action",
        "route.flow",
        "execution.plan",
    ]
    assert graph["nodes"][0]["label"] == "concept_cleas"
    assert graph["nodes"][1]["label"] == "knowledge_lookup"
    assert graph["nodes"][2]["label"] == "knowledge_lookup"


def test_runtime_trace_includes_decision_graph_operation():
    runtime = build_galicia_runtime()

    runtime.process(Event(type="user_message", payload="quiero hablar con un asesor"))
    trace = runtime.last_trace()

    assert trace is not None
    assert "DECISION_GRAPH" in trace.operations()
    decision_events = [event for event in trace.events if event.operation == "DECISION_GRAPH"]
    assert decision_events[-1].component == "decision_graph_engine"


def test_runtime_event_bus_observes_decision_graph_creation():
    runtime = build_galicia_runtime()

    runtime.process(Event(type="user_message", payload="estado de mi siniestro"))

    event_types = [event.type for event in runtime.event_bus.events()]
    assert "runtime.decision_graph_created" in event_types
