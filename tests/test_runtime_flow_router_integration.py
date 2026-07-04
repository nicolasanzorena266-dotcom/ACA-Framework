from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime


def _runtime() -> ACAOSRuntime:
    return ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )


def test_runtime_records_execution_flow_in_facts():
    state = _runtime().process(Event(type="user_message", payload="Que es CLEAS?"))

    assert state.facts["zero_cost_action_plan"]["action"] == "knowledge_lookup"
    assert state.facts["zero_cost_execution_flow"]["flow"] == "knowledge_lookup"
    assert state.facts["zero_cost_execution_flow"]["payload"]["tool_key"] == "cleas"


def test_runtime_timeline_includes_flow_route_operation():
    output = _runtime().process_output(
        Event(type="user_message", payload="Necesito hablar con un asesor")
    )

    operations = [entry["operation"] for entry in output.trace]
    assert "ACTION_PLAN" in operations
    assert "FLOW_ROUTE" in operations
