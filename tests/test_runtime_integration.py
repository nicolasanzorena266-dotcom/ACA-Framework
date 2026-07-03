from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime
from aca_os.tool_engine import StaticKnowledgeAdapter, ToolEngine


def build_runtime():
    tool_engine = ToolEngine()
    tool_engine.register(
        StaticKnowledgeAdapter(
            {
                "cleas": {
                    "summary": "Convenio entre aseguradoras para resolver ciertos siniestros automotores."
                }
            }
        )
    )

    return ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
        tool_engine=tool_engine,
        domain_context={"domain": "galicia"},
    )


def test_runtime_integrates_tool_evidence_and_context_bundle():
    runtime = build_runtime()

    state = runtime.process(Event(type="user_message", payload="Que es el convenio CLEAS?"))

    assert state.tool_evidence["cleas"]["summary"].startswith("Convenio entre aseguradoras")
    assert state.context_bundle["tool_evidence"]["cleas"]["summary"].startswith("Convenio entre aseguradoras")
    assert state.context_bundle["domain_context"]["domain"] == "galicia"


def test_runtime_still_processes_auto_claim_flow():
    runtime = build_runtime()

    state = runtime.process(Event(type="user_message", payload="Me chocaron ayer y el tercero no hizo la denuncia"))

    assert state.active_mission["type"] == "auto_claim_guidance"
    assert state.facts["event_type"] == "vehicle_collision"
    assert state.response
    assert state.context_bundle["mission"]["type"] == "auto_claim_guidance"
