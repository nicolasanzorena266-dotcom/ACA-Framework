from aca_kernel.core.events import Event
from sdk.factory import build_galicia_runtime, process_message


def test_runtime_introspection_snapshot_exposes_components_and_metrics():
    runtime = build_galicia_runtime()
    runtime.process(Event(type="user_message", payload="Que es CLEAS?", metadata={"conversation_id": "inspect-test"}))

    snapshot = runtime.inspect_runtime().to_dict()

    component_names = [component["name"] for component in snapshot["components"]]
    assert snapshot["status"] == "ready"
    assert "intent_matcher" in component_names
    assert "event_bus" in component_names
    assert snapshot["last_state"]["conversation_id"] == "inspect-test"
    assert snapshot["metrics"]["trace_count"] == 1
    assert snapshot["metrics"]["runtime_event_count"] > 0


def test_runtime_introspection_trace_contract_is_stable():
    runtime = build_galicia_runtime()
    runtime.process(Event(type="user_message", payload="Necesito hablar con un asesor"))

    trace_data = runtime.introspection.inspect_trace()

    assert trace_data["trace_id"] == runtime.last_trace().trace_id
    assert "INTENT_MATCH" in trace_data["operations"]
    assert "runtime.process.completed" in trace_data["operations"]


def test_process_message_can_include_introspection_snapshot():
    result = process_message("Que es la franquicia?", conversation_id="sdk-inspect", include_introspection=True)

    snapshot = result["introspection"]
    assert snapshot["last_state"]["conversation_id"] == "sdk-inspect"
    assert snapshot["last_trace"]["event_count"] > 0
    assert "runtime.execution_plan_created" in snapshot["event_bus"]["event_types"]
