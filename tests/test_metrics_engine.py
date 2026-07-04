from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.execution_trace import ExecutionTrace, TraceEvent
from aca_os.metrics_engine import MetricsEngine, build_metrics_from_trace
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime


def test_metrics_engine_builds_snapshot_from_execution_trace():
    trace = ExecutionTrace(
        trace_id="trace-1",
        conversation_id="conv-1",
        runtime_id="runtime-1",
        started_at="start",
        finished_at="finish",
        duration_ms=10.0,
        events=[
            TraceEvent(index=0, component="intent_matcher", operation="INTENT_MATCH", duration_ms=1.0),
            TraceEvent(index=1, component="intent_matcher", operation="INTENT_MATCH", duration_ms=3.0),
            TraceEvent(index=2, component="policy_manager", operation="POLICY_RESULT", duration_ms=2.0),
        ],
    )

    snapshot = build_metrics_from_trace(trace).to_dict()

    assert snapshot["runtime_id"] == "runtime-1"
    assert snapshot["trace_count"] == 1
    assert snapshot["event_count"] == 3
    assert snapshot["total_duration_ms"]["p95"] == 10.0
    assert snapshot["components"]["intent_matcher"]["event_count"] == 2
    assert snapshot["components"]["intent_matcher"]["duration_ms"]["avg"] == 2.0


def test_metrics_engine_supports_manual_counters_and_gauges():
    engine = MetricsEngine()

    engine.increment("component.custom.invocations")
    engine.increment("component.custom.invocations", 2)
    engine.set_gauge("runtime.queue_depth", 4)

    snapshot = engine.snapshot(runtime_id="runtime-1").to_dict()

    assert snapshot["counters"]["component.custom.invocations"]["value"] == 3
    assert snapshot["gauges"]["runtime.queue_depth"]["value"] == 4.0


def test_runtime_exports_metrics_without_ui_logic():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    runtime.process(Event(type="user_message", payload="Que es la franquicia?"))
    metrics = runtime.export_metrics()

    assert metrics["trace_count"] == 1
    assert metrics["process_count"] == 1
    assert metrics["event_count"] > 0
    assert "intent_matcher" in metrics["components"]
    assert metrics["counters"]["runtime.trace_count"]["value"] == 1


def test_introspection_uses_metrics_engine_snapshot():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    runtime.process(Event(type="user_message", payload="Que es CLEAS?"))
    snapshot = runtime.export_introspection()

    assert snapshot["metrics"]["trace_count"] == 1
    assert snapshot["metrics"]["total_duration_ms"]["count"] == 1
    assert "metrics_engine" in {component["name"] for component in snapshot["components"]}
