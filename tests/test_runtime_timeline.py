from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.event_bus import EventBus
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime
from aca_os.runtime_timeline import RuntimeTimeline
from sdk.factory import build_galicia_runtime


def test_runtime_timeline_normalizes_state_transitions():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    state = runtime.process(Event(type="user_message", payload="Que es la franquicia?"))
    timeline = RuntimeTimeline.from_state(state)

    assert timeline.entries
    assert timeline.entries[0].kind == "state_transition"
    assert "INTENT_MATCH" in timeline.operations()
    assert "ACTION_PLAN" in timeline.operations()
    assert "EXECUTION_PLAN" in timeline.operations()


def test_runtime_timeline_can_include_runtime_events():
    bus = EventBus()
    runtime = build_galicia_runtime(event_bus=bus)

    state = runtime.process(Event(type="user_message", payload="Que es CLEAS?"))
    timeline = RuntimeTimeline.from_state(state, bus.events())

    event_entries = [entry for entry in timeline.entries if entry.kind == "runtime_event"]
    assert event_entries
    assert "runtime.execution_plan_created" in timeline.operations()


def test_output_exposes_runtime_timeline_without_breaking_trace():
    runtime = build_galicia_runtime()

    output = runtime.process_output(Event(type="user_message", payload="Necesito hablar con un asesor"))
    data = output.to_dict()

    assert data["trace"]
    assert data["runtime_timeline"]["entries"]
    assert "ACTION_PLAN" in data["runtime_timeline"]["operations"]
    assert "runtime.process.completed" in data["runtime_timeline"]["operations"]
