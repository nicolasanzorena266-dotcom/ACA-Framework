from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.event_bus import EventBus
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime
from sdk.factory import build_galicia_runtime


def test_runtime_emits_observable_decision_events_without_changing_facts():
    bus = EventBus()
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
        event_bus=bus,
    )

    state = runtime.process(Event(type="user_message", payload="Que es la franquicia?"))

    event_types = [event.type for event in bus.events()]
    assert "runtime.intent_matched" in event_types
    assert "runtime.action_planned" in event_types
    assert "runtime.flow_routed" in event_types
    assert "runtime.execution_plan_created" in event_types
    assert "runtime.process.completed" in event_types
    assert "zero_cost_action_plan" in state.facts
    assert "zero_cost_execution_plan" in state.facts


def test_galicia_runtime_event_bus_observes_execution_plan():
    bus = EventBus()
    runtime = build_galicia_runtime(event_bus=bus)

    runtime.process(Event(type="user_message", payload="Que es CLEAS?"))

    execution_events = [
        event for event in bus.events() if event.type == "runtime.execution_plan_created"
    ]
    assert execution_events
    assert execution_events[-1].payload["execution_plan"]["steps"]
