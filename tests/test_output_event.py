from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.mission_manager import MissionManager
from aca_os.output import ACAOutput
from aca_os.runtime import ACAOSRuntime


def test_output_event_can_be_created_from_state():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    state = runtime.process(Event(type="user_message", payload="Me chocaron ayer"))
    output = ACAOutput.from_state(state)

    assert output.response
    assert output.mission["type"] == "auto_claim_guidance"
    assert output.trace


def test_runtime_can_return_output_event():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    output = runtime.process_output(Event(type="user_message", payload="Hola"))

    assert output.response
    assert output.conversation_id
    assert output.trace