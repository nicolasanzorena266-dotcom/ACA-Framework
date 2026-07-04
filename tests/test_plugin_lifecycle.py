import json
from pathlib import Path

import pytest

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.component_registry import ComponentRegistry, ComponentState
from aca_os.mission_manager import MissionManager
from aca_os.plugin_lifecycle import PluginLifecycleManager, PluginLifecycleState
from aca_os.plugin_loader import PluginLoader
from aca_os.runtime import ACAOSRuntime


def _payload(name="demo.plugin"):
    return {
        "manifest_version": "1",
        "name": name,
        "version": "0.1.0",
        "provider": "aca-labs",
        "runtime": {"min_version": "0.3.0"},
        "entrypoint": {"module": "demo_plugin.main", "factory": "create_plugin"},
        "capabilities": [{"name": "demo.answer", "kind": "tool"}],
        "permissions": [{"name": "trace.read", "reason": "Read execution trace"}],
        "dependencies": [],
        "tags": ["example"],
        "metadata": {"test": True},
    }


def _write_manifest(root: Path, payload: dict):
    root.mkdir(parents=True, exist_ok=True)
    path = root / "plugin.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _manager():
    registry = ComponentRegistry()
    loader = PluginLoader(component_registry=registry)
    lifecycle = PluginLifecycleManager(component_registry=registry, plugin_loader=loader)
    return registry, lifecycle


def test_plugin_lifecycle_attaches_loaded_plugins_as_registered(tmp_path):
    _write_manifest(tmp_path / "demo", _payload())
    registry, lifecycle = _manager()

    load = lifecycle.load_plugins(str(tmp_path))
    snapshot = lifecycle.snapshot()

    assert load["loaded_count"] == 1
    assert snapshot.plugin_count == 1
    assert snapshot.records[0].state == PluginLifecycleState.REGISTERED
    assert registry.require("demo.plugin").state == ComponentState.REGISTERED
    assert snapshot.events[0].action == "register"


def test_plugin_lifecycle_moves_component_registry_state(tmp_path):
    _write_manifest(tmp_path / "demo", _payload())
    registry, lifecycle = _manager()
    lifecycle.load_plugins(str(tmp_path))

    lifecycle.initialize("demo.plugin")
    lifecycle.activate("demo.plugin")
    lifecycle.pause("demo.plugin")
    lifecycle.stop("demo.plugin")

    assert registry.require("demo.plugin").state == ComponentState.STOPPED
    assert lifecycle.require("demo.plugin").state == PluginLifecycleState.STOPPED
    assert [event.to_state for event in lifecycle.events()] == [
        "registered",
        "initialized",
        "active",
        "paused",
        "stopped",
    ]


def test_plugin_lifecycle_rejects_invalid_transition(tmp_path):
    _write_manifest(tmp_path / "demo", _payload())
    registry, lifecycle = _manager()
    lifecycle.load_plugins(str(tmp_path))

    with pytest.raises(ValueError):
        lifecycle.activate("demo.plugin")

    assert lifecycle.require("demo.plugin").state == PluginLifecycleState.REGISTERED
    assert lifecycle.events()[-1].success is False


def test_plugin_lifecycle_unloads_non_active_plugin(tmp_path):
    _write_manifest(tmp_path / "demo", _payload())
    registry, lifecycle = _manager()
    lifecycle.load_plugins(str(tmp_path))
    lifecycle.initialize("demo.plugin")
    lifecycle.stop("demo.plugin")

    record = lifecycle.unload("demo.plugin")

    assert record.state == PluginLifecycleState.UNLOADED
    assert registry.get("demo.plugin") is None
    assert lifecycle.snapshot().states["unloaded"] == 1


def test_plugin_lifecycle_refuses_to_unload_active_plugin(tmp_path):
    _write_manifest(tmp_path / "demo", _payload())
    registry, lifecycle = _manager()
    lifecycle.load_plugins(str(tmp_path))
    lifecycle.initialize("demo.plugin")
    lifecycle.activate("demo.plugin")

    with pytest.raises(ValueError):
        lifecycle.unload("demo.plugin")

    assert registry.require("demo.plugin").state == ComponentState.ACTIVE


def test_plugin_lifecycle_exports_json_snapshot(tmp_path):
    _write_manifest(tmp_path / "demo", _payload())
    _, lifecycle = _manager()
    lifecycle.load_plugins(str(tmp_path))

    exported = json.loads(lifecycle.export(format="json"))

    assert exported["contract"] == "plugin_lifecycle.v1"
    assert exported["states"] == {"registered": 1}


def test_runtime_exposes_plugin_lifecycle_boundary(tmp_path):
    _write_manifest(tmp_path / "demo", _payload())
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    load = runtime.load_plugins(str(tmp_path))
    runtime.initialize_plugin("demo.plugin")
    runtime.activate_plugin("demo.plugin")
    lifecycle = runtime.export_plugin_lifecycle()
    plugins = runtime.export_plugins()

    assert load["lifecycle"]["plugin_count"] == 1
    assert lifecycle["states"] == {"active": 1}
    assert plugins["lifecycle"]["records"][0]["state"] == "active"
    assert runtime.component_registry.require("plugin_lifecycle").state == ComponentState.ACTIVE
