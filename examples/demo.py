from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime

runtime = ACAOSRuntime(
    kernel=ACAKernel(build_default_registry()),
    compiler=GraphCompiler(),
    mission_manager=MissionManager(),
)

state = runtime.process(Event(type="user_message", payload="Me chocaron ayer y el tercero no hizo la denuncia"))
print(state.response)
print(state.to_dict())
