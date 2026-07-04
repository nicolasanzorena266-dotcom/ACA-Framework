from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime


def test_runtime_stores_zero_cost_action_plan_in_facts():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    state = runtime.process(Event(type="user_message", payload="Que es la franquicia?"))

    action_plan = state.facts["zero_cost_action_plan"]
    assert action_plan["action"] == "knowledge_lookup"
    assert action_plan["source_intent"] == "concept_franquicia"
    assert action_plan["payload"]["tool_key"] == "franquicia"


def test_runtime_action_plan_is_visible_in_trace():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    output = runtime.process_output(Event(type="user_message", payload="Necesito hablar con un asesor"))

    operations = [item["operation"] for item in output.trace]
    assert "ACTION_PLAN" in operations
