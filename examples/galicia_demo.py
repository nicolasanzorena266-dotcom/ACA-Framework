from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime
from aca_os.tool_engine import StaticKnowledgeAdapter, ToolEngine
from domains.galicia.domain_pack import load_galicia_domain


domain = load_galicia_domain()

tool_engine = ToolEngine()
tool_engine.register(
    StaticKnowledgeAdapter(
        {
            "cleas": domain.concepts["cleas"],
            "franquicia": domain.concepts["franquicia"],
            "denuncia_administrativa": domain.concepts["denuncia_administrativa"],
        }
    )
)

runtime = ACAOSRuntime(
    kernel=ACAKernel(build_default_registry()),
    compiler=GraphCompiler(),
    mission_manager=MissionManager(),
    tool_engine=tool_engine,
    domain_context=domain.context(),
)

state = runtime.process(Event(type="user_message", payload="Que es el convenio CLEAS?"))

print(state.response)
print(state.context_bundle)