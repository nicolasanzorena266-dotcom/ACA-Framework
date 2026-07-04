import json
from pathlib import Path

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.component_registry import ComponentRegistry
from aca_os.domain_pack_examples import (
    EXAMPLE_DOMAIN_PACKS_CONTRACT,
    discover_example_domain_pack_manifests,
    example_domain_pack_catalog,
    example_domain_pack_root,
    load_example_domain_pack_manifests,
    load_example_domain_packs,
)
from aca_os.domain_pack_loader import DomainPackLoader
from aca_os.domain_pack_validator import DomainPackValidator
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime


EXPECTED_EXAMPLE_PACKS = {"example.customer_support", "example.operations_basic"}


def test_example_domain_pack_root_is_data_only():
    root = example_domain_pack_root()

    assert root.exists()
    assert {path.parent.name for path in discover_example_domain_pack_manifests()} == {
        "customer_support",
        "operations_basic",
    }
    assert not list(root.rglob("*.py"))


def test_example_domain_pack_manifests_parse_deterministically():
    manifests = load_example_domain_pack_manifests()

    assert {manifest.name for manifest in manifests} == EXPECTED_EXAMPLE_PACKS
    assert [manifest.name for manifest in manifests] == sorted(manifest.name for manifest in manifests)
    assert all(manifest.metadata["executes_on_load"] is False for manifest in manifests)
    assert all(manifest.metadata["domain_code_imported"] is False for manifest in manifests)


def test_example_domain_pack_assets_are_present_and_json_assets_are_parseable():
    for manifest_path in discover_example_domain_pack_manifests():
        manifest = load_example_domain_pack_manifests(manifest_path)[0]
        for asset in manifest.assets:
            asset_path = manifest_path.parent / asset.path
            assert asset_path.exists(), asset.path
            if asset.format == "json":
                payload = json.loads(asset_path.read_text(encoding="utf-8"))
                assert payload["schema"].startswith("aca.domain_pack.")


def test_example_domain_pack_validator_accepts_all_bundled_examples():
    validator = DomainPackValidator()

    results = [validator.validate_manifest_file(path) for path in discover_example_domain_pack_manifests()]
    snapshot = validator.snapshot()

    assert all(result.valid for result in results)
    assert snapshot.validation_count == 2
    assert snapshot.valid_count == 2
    assert snapshot.invalid_count == 0


def test_example_domain_pack_loader_registers_examples_through_component_registry():
    registry = ComponentRegistry()
    # Example packs intentionally declare runtime service dependencies, so the
    # test uses the real runtime registry for dependency-aware loading below.
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )
    loader = DomainPackLoader(component_registry=runtime.component_registry)

    snapshot = load_example_domain_packs(loader)

    assert snapshot.loaded_count == 2
    assert snapshot.failed_count == 0
    assert EXPECTED_EXAMPLE_PACKS.issubset(
        {descriptor.name for descriptor in runtime.component_registry.list()}
    )
    assert runtime.component_registry.require("example.customer_support").metadata["domain_code_imported"] is False
    assert runtime.component_registry.require("example.operations_basic").metadata["domain_code_imported"] is False
    assert registry.list() == []


def test_runtime_loads_bundled_example_domain_packs():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    snapshot = runtime.load_domain_packs(str(example_domain_pack_root()))
    components = runtime.export_components()["components"]

    assert snapshot["loaded_count"] == 2
    assert {"example.customer_support", "example.operations_basic"}.issubset(
        {component["name"] for component in components}
    )
    assert runtime.component_registry.find_by_capability("domain.customer_support.intent_catalog")
    assert runtime.component_registry.find_by_capability("domain.operations.metric_catalog")


def test_example_domain_pack_catalog_is_observable_and_stable():
    catalog = example_domain_pack_catalog()

    assert catalog["contract"] == EXAMPLE_DOMAIN_PACKS_CONTRACT
    assert catalog["pack_count"] == 2
    assert [pack["name"] for pack in catalog["packs"]] == sorted(
        pack["name"] for pack in catalog["packs"]
    )
    assert catalog["packs"][0]["metadata"]["example"] is True
