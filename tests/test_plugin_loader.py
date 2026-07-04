import json
from pathlib import Path

import pytest

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.component_registry import ComponentRegistry, ComponentState
from aca_os.mission_manager import MissionManager
from aca_os.plugin_loader import PluginLoadStatus, PluginLoader
from aca_os.runtime import ACAOSRuntime


def _payload(name="demo.plugin", dependency="metrics_engine"):
    return {
        "manifest_version": "1",
        "name": name,
        "version": "0.1.0",
        "provider": "aca-labs",
        "runtime": {"min_version": "0.3.0"},
        "entrypoint": {"module": "demo_plugin.main", "factory": "create_plugin"},
        "capabilities": [{"name": "demo.answer", "kind": "tool"}],
        "permissions": ["trace.read"],
        "dependencies": [dependency] if dependency else [],
        "tags": ["example"],
        "metadata": {"test": True},
    }


def _write_manifest(root: Path, payload: dict):
    root.mkdir(parents=True, exist_ok=True)
    path = root / "plugin.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_plugin_loader_discovers_manifests_deterministically(tmp_path):
    _write_manifest(tmp_path / "b_plugin", _payload(name="b.plugin", dependency=None))
    _write_manifest(tmp_path / "a_plugin", _payload(name="a.plugin", dependency=None))

    loader = PluginLoader(component_registry=ComponentRegistry())
    discovered = [path.parent.name for path in loader.discover(tmp_path)]

    assert discovered == ["a_plugin", "b_plugin"]


def test_plugin_loader_loads_manifest_into_component_registry_without_importing_entrypoint(tmp_path):
    manifest_path = _write_manifest(tmp_path / "demo", _payload(dependency=None))
    registry = ComponentRegistry()
    loader = PluginLoader(component_registry=registry)

    snapshot = loader.load(manifest_path)

    assert snapshot.loaded_count == 1
    assert snapshot.failed_count == 0
    assert registry.require("demo.plugin").state == ComponentState.REGISTERED
    assert registry.require("demo.plugin").metadata["entrypoint_imported"] is False
    assert registry.find_by_capability("demo.answer")[0].name == "demo.plugin"


def test_plugin_loader_reports_invalid_manifest_without_corrupting_registry(tmp_path):
    bad_path = _write_manifest(tmp_path / "bad", _payload(dependency=None))
    payload = json.loads(bad_path.read_text(encoding="utf-8"))
    payload.pop("entrypoint")
    bad_path.write_text(json.dumps(payload), encoding="utf-8")
    registry = ComponentRegistry()
    loader = PluginLoader(component_registry=registry)

    snapshot = loader.load(tmp_path)

    assert snapshot.loaded_count == 0
    assert snapshot.failed_count == 1
    assert registry.get("demo.plugin") is None
    assert "entrypoint" in snapshot.results[0].errors[0]


def test_plugin_loader_uses_component_registry_dependency_validation(tmp_path):
    _write_manifest(tmp_path / "demo", _payload(dependency="missing_runtime_component"))
    registry = ComponentRegistry()
    loader = PluginLoader(component_registry=registry)

    snapshot = loader.load(tmp_path)

    assert snapshot.failed_count == 1
    assert "missing dependencies" in snapshot.results[0].errors[0]


def test_plugin_loader_skips_duplicate_plugin_names(tmp_path):
    manifest_path = _write_manifest(tmp_path / "demo", _payload(dependency=None))
    registry = ComponentRegistry()
    loader = PluginLoader(component_registry=registry)

    first = loader.load(manifest_path)
    second = loader.load(manifest_path)

    assert first.loaded_count == 1
    assert second.skipped_count == 1
    assert second.results[0].status == PluginLoadStatus.SKIPPED


def test_runtime_loads_plugins_through_registry_boundary(tmp_path):
    _write_manifest(tmp_path / "demo", _payload())
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    snapshot = runtime.load_plugins(str(tmp_path))
    plugins = runtime.export_plugins()
    components = runtime.export_components()

    assert snapshot["loaded_count"] == 1
    assert plugins["loaded_count"] == 1
    assert "demo.plugin" in {item["name"] for item in components["components"]}
    assert runtime.component_registry.require("plugin_loader").state == ComponentState.ACTIVE
