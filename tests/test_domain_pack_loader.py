import json
from pathlib import Path

import pytest

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.component_registry import ComponentRegistry, ComponentState
from aca_os.domain_pack_loader import DomainPackLoader, DomainPackLoadStatus
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime


def _payload(name="demo.claims", dependency="policy_manager"):
    return {
        "manifest_version": "1",
        "name": name,
        "version": "0.1.0",
        "domain": "insurance.claims",
        "description": "Demo deterministic claims domain pack",
        "provider": "aca-labs",
        "runtime": {"min_version": "0.3.0"},
        "capabilities": [
            {"name": "domain.concepts.lookup", "kind": "knowledge"},
            "domain.policy.context",
        ],
        "assets": [
            {"name": "concepts", "kind": "concepts", "path": "concepts", "format": "json-dir"},
            {"name": "policies", "kind": "policies", "path": "policies", "format": "json-dir"},
            {
                "name": "scenarios",
                "kind": "scenarios",
                "path": "scenarios",
                "format": "json-dir",
                "required": False,
            },
        ],
        "dependencies": [dependency] if dependency else [],
        "tags": ["example"],
        "metadata": {"test": True},
    }


def _write_pack(root: Path, payload: dict):
    root.mkdir(parents=True, exist_ok=True)
    (root / "concepts").mkdir(exist_ok=True)
    (root / "policies").mkdir(exist_ok=True)
    path = root / "domain_pack.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_domain_pack_loader_discovers_manifests_deterministically(tmp_path):
    _write_pack(tmp_path / "b_pack", _payload(name="b.pack", dependency=None))
    _write_pack(tmp_path / "a_pack", _payload(name="a.pack", dependency=None))

    loader = DomainPackLoader(component_registry=ComponentRegistry())
    discovered = [path.parent.name for path in loader.discover(tmp_path)]

    assert discovered == ["a_pack", "b_pack"]


def test_domain_pack_loader_loads_manifest_into_component_registry_without_importing_domain_code(tmp_path):
    manifest_path = _write_pack(tmp_path / "demo", _payload(dependency=None))
    registry = ComponentRegistry()
    loader = DomainPackLoader(component_registry=registry)

    snapshot = loader.load(manifest_path)

    assert snapshot.loaded_count == 1
    assert snapshot.failed_count == 0
    assert registry.require("demo.claims").state == ComponentState.REGISTERED
    assert registry.require("demo.claims").metadata["domain_code_imported"] is False
    assert registry.find_by_capability("domain.policy.context")[0].name == "demo.claims"


def test_domain_pack_loader_reports_invalid_manifest_without_corrupting_registry(tmp_path):
    bad_path = _write_pack(tmp_path / "bad", _payload(dependency=None))
    payload = json.loads(bad_path.read_text(encoding="utf-8"))
    payload["domain"] = ""
    bad_path.write_text(json.dumps(payload), encoding="utf-8")
    registry = ComponentRegistry()
    loader = DomainPackLoader(component_registry=registry)

    snapshot = loader.load(tmp_path)

    assert snapshot.loaded_count == 0
    assert snapshot.failed_count == 1
    assert registry.get("demo.claims") is None
    assert "domain" in snapshot.results[0].errors[0]


def test_domain_pack_loader_checks_required_assets_at_load_boundary(tmp_path):
    root = tmp_path / "bad_assets"
    root.mkdir()
    path = root / "domain_pack.json"
    path.write_text(json.dumps(_payload(dependency=None)), encoding="utf-8")
    registry = ComponentRegistry()
    loader = DomainPackLoader(component_registry=registry)

    snapshot = loader.load(path)

    assert snapshot.failed_count == 1
    assert "Missing required Domain Pack assets" in snapshot.results[0].errors[0]
    assert "concepts" in snapshot.results[0].errors[0]


def test_domain_pack_loader_uses_component_registry_dependency_validation(tmp_path):
    _write_pack(tmp_path / "demo", _payload(dependency="missing_runtime_component"))
    registry = ComponentRegistry()
    loader = DomainPackLoader(component_registry=registry)

    snapshot = loader.load(tmp_path)

    assert snapshot.failed_count == 1
    assert "missing dependencies" in snapshot.results[0].errors[0]


def test_domain_pack_loader_skips_duplicate_pack_names(tmp_path):
    manifest_path = _write_pack(tmp_path / "demo", _payload(dependency=None))
    registry = ComponentRegistry()
    loader = DomainPackLoader(component_registry=registry)

    first = loader.load(manifest_path)
    second = loader.load(manifest_path)

    assert first.loaded_count == 1
    assert second.skipped_count == 1
    assert second.results[0].status == DomainPackLoadStatus.SKIPPED


def test_domain_pack_loader_exports_observable_snapshot(tmp_path):
    _write_pack(tmp_path / "demo", _payload(dependency=None))
    registry = ComponentRegistry()
    loader = DomainPackLoader(component_registry=registry)
    loader.load(tmp_path)

    exported = loader.export(format="dict")
    exported_json = json.loads(loader.export(format="json"))

    assert exported["contract"] == "domain_pack_loader.v1"
    assert exported["loaded_count"] == 1
    assert exported_json["results"][0]["manifest"]["name"] == "demo.claims"


def test_runtime_loads_domain_packs_through_registry_boundary(tmp_path):
    _write_pack(tmp_path / "demo", _payload())
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    snapshot = runtime.load_domain_packs(str(tmp_path))
    packs = runtime.export_domain_packs()
    components = runtime.export_components()

    assert snapshot["loaded_count"] == 1
    assert packs["loaded_count"] == 1
    assert "demo.claims" in {item["name"] for item in components["components"]}
    assert runtime.component_registry.require("domain_pack_loader").state == ComponentState.ACTIVE
