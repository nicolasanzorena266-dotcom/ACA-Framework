from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime


def test_runtime_stores_intent_match_in_state_and_output():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    output = runtime.process_output(Event(type="user_message", payload="Que es la franquicia?"))

    assert output.intent_match["intent"] == "concept_franquicia"
    assert output.to_dict()["intent_match"]["intent"] == "concept_franquicia"