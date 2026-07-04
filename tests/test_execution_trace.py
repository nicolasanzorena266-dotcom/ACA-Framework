from aca_kernel.core.events import Event
from aca_os.execution_trace import ExecutionTrace, sanitize
from sdk.factory import build_galicia_runtime


def test_execution_trace_is_created_for_runtime_execution():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="Que es CLEAS?"))
    trace = runtime.last_trace()

    assert trace is not None
    assert trace.conversation_id == state.conversation_id
    assert trace.runtime_id == runtime.runtime_id
    assert trace.duration_ms >= 0
    assert "INTENT_MATCH" in trace.operations()
    assert "ACTION_PLAN" in trace.operations()
    assert "EXECUTION_PLAN" in trace.operations()


def test_execution_trace_can_be_retrieved_by_id_and_exported():
    runtime = build_galicia_runtime()

    runtime.process(Event(type="user_message", payload="Necesito hablar con un asesor"))
    trace = runtime.last_trace()

    assert trace is not None
    assert runtime.trace(trace.trace_id) == trace
    exported = runtime.export_trace(trace.trace_id)
    assert exported["trace_id"] == trace.trace_id
    assert exported["events"]


def test_trace_sanitizer_bounds_nested_payloads():
    payload = {"items": list(range(40)), "deep": {"a": {"b": {"c": {"d": "stop"}}}}}

    sanitized = sanitize(payload, max_depth=3, max_items=3)

    assert sanitized["items"][-1].startswith("<truncated:")
    assert sanitized["deep"]["a"]["b"] == "<max-depth>"
