from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime
from aca_os.tool_engine import StaticKnowledgeAdapter, ToolEngine
from domains.galicia.domain_pack import load_galicia_domain


def build_galicia_runtime():
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

    return ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
        tool_engine=tool_engine,
        domain_context=domain.context(),
    )


def test_domain_policy_uses_concept_lookup_for_franquicia():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="Que es la franquicia?"))

    assert state.policy_result["decision"] == "USE_TOOL"
    assert state.policy_result["tool_key"] == "franquicia"
    assert state.tool_evidence["franquicia"]["name"] == "Franquicia"


def test_domain_policy_escalates_real_claim_status():
    runtime = build_galicia_runtime()

    state = runtime.process(Event(type="user_message", payload="Ya aprobaron mi indemnizacion?"))

    assert state.policy_result["decision"] == "ESCALATE"
    assert "no_crm_access" in state.policy_result["triggered_rules"]
    assert "No tengo acceso al expediente" in state.response