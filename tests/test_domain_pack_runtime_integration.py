from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.domain_pack_examples import example_domain_pack_root
from aca_os.domain_pack_runtime import DOMAIN_PACK_RUNTIME_CONTRACT, DomainPackRuntime
from aca_os.domain_pack_loader import DomainPackLoader
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime


def _runtime() -> ACAOSRuntime:
    return ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )


def test_domain_pack_runtime_loads_assets_as_data_without_importing_domain_code():
    runtime = DomainPackRuntime(DomainPackLoader())
    loader = DomainPackLoader()
    # bind through a real ACA runtime registry so example dependencies resolve.
    aca = _runtime()
    runtime = DomainPackRuntime(aca.domain_pack_loader)

    snapshot = runtime.load(example_domain_pack_root())
    support = runtime.get("example.customer_support")

    assert snapshot.contract == DOMAIN_PACK_RUNTIME_CONTRACT
    assert snapshot.pack_count == 2
    assert support.asset("intents").content["schema"] == "aca.domain_pack.intents.v1"
    assert support.metadata["domain_code_imported"] is False
    assert "support.status_request" in {item["name"] for item in support.asset("intents").content["intents"]}


def test_runtime_integrates_domain_pack_context_into_context_bundle():
    runtime = _runtime()

    snapshot = runtime.load_domain_packs(str(example_domain_pack_root()))
    output = runtime.process_output(
        Event(type="user_message", payload="Check ticket 12345", metadata={"conversation_id": "domain-runtime"})
    )
    context = output.context_bundle["domain_context"]["domain_packs"]

    assert snapshot["contract"] == DOMAIN_PACK_RUNTIME_CONTRACT
    assert context["pack_count"] == 2
    assert "customer.support" in context["domains"]
    assert "domain.customer_support.intent_catalog" in context["capabilities"]
    assert context["domains"]["customer.support"]["assets"]["intents"]["schema"] == "aca.domain_pack.intents.v1"


def test_runtime_exports_domain_pack_snapshot_and_individual_pack():
    runtime = _runtime()
    runtime.load_domain_packs(str(example_domain_pack_root()))

    exported = runtime.export_domain_packs()
    pack = runtime.get_domain_pack("example.operations_basic")
    context = runtime.export_domain_pack_context()

    assert exported["pack_count"] == 2
    assert pack["pack"]["domain"] == "operations.basic"
    assert context["packs"]["example.operations_basic"]["assets"]["metrics"]["schema"] == "aca.domain_pack.metrics.v1"


def test_domain_pack_runtime_boundary_is_registered_as_component():
    runtime = _runtime()

    descriptor = runtime.component_registry.require("domain_pack_runtime")

    assert descriptor.state.value == "active"
    assert "domain_pack.runtime.context" in descriptor.capabilities
