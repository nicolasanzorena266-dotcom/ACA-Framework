import json

import pytest

from aca_os.component_registry import ComponentRegistry, ComponentState
from aca_os.plugin_manifest import (
    PluginContract,
    PluginManifest,
    SUPPORTED_MANIFEST_VERSION,
    build_plugin_contract,
)


def _manifest_payload():
    return {
        "manifest_version": SUPPORTED_MANIFEST_VERSION,
        "name": "demo.plugin",
        "version": "0.1.0",
        "description": "Demo plugin contract",
        "provider": "aca-labs",
        "runtime": {"min_version": "0.3.0", "max_version": "0.4.0"},
        "entrypoint": {"module": "demo_plugin.main", "factory": "create_plugin"},
        "capabilities": [
            {"name": "demo.answer", "kind": "tool", "description": "Answer demo questions"},
            "demo.explain",
        ],
        "permissions": [
            {"name": "memory.read", "reason": "Read relevant runtime memory"},
            "trace.read",
        ],
        "hooks": [{"name": "on_register", "target": "demo_plugin.hooks:on_register"}],
        "dependencies": ["metrics_engine"],
        "tags": ["example", "sdk"],
        "metadata": {"owner": "tests"},
    }


def test_plugin_manifest_parses_contract_metadata():
    manifest = PluginManifest.from_dict(_manifest_payload())

    assert manifest.name == "demo.plugin"
    assert manifest.entrypoint.module == "demo_plugin.main"
    assert manifest.capability_names() == ("demo.answer", "demo.explain")
    assert manifest.permission_names() == ("memory.read", "trace.read")
    assert manifest.hook_names() == ("on_register",)
    assert manifest.runtime.min_version == "0.3.0"


def test_plugin_manifest_round_trips_json_deterministically():
    manifest = PluginManifest.from_dict(_manifest_payload())
    restored = PluginManifest.from_json(manifest.to_json())

    assert restored.to_dict() == manifest.to_dict()
    assert json.loads(restored.to_json())["name"] == "demo.plugin"


def test_plugin_manifest_rejects_invalid_manifest_version():
    payload = _manifest_payload()
    payload["manifest_version"] = "99"

    with pytest.raises(ValueError, match="Unsupported plugin manifest version"):
        PluginManifest.from_dict(payload)


def test_plugin_manifest_requires_entrypoint_without_importing_code():
    payload = _manifest_payload()
    payload.pop("entrypoint")

    with pytest.raises(ValueError, match="entrypoint"):
        PluginManifest.from_dict(payload)


def test_plugin_manifest_rejects_duplicate_capabilities():
    payload = _manifest_payload()
    payload["capabilities"] = ["demo.answer", "demo.answer"]

    with pytest.raises(ValueError, match="capability"):
        PluginManifest.from_dict(payload)


def test_plugin_contract_projects_to_component_descriptor():
    contract = build_plugin_contract(_manifest_payload())
    component = contract.component

    assert isinstance(contract, PluginContract)
    assert component.name == "demo.plugin"
    assert component.role == "plugin"
    assert component.class_name == "PluginManifest"
    assert component.state == ComponentState.REGISTERED
    assert "demo.answer" in component.capabilities
    assert "plugin" in component.tags
    assert component.metadata["entrypoint"]["module"] == "demo_plugin.main"


def test_plugin_descriptor_can_enter_component_registry_after_dependencies_exist():
    registry = ComponentRegistry()
    registry.register_instance(
        name="metrics_engine",
        instance=object(),
        role="runtime metrics aggregation",
        capabilities=("metrics.snapshot",),
    )

    descriptor = PluginManifest.from_dict(_manifest_payload()).to_component_descriptor()
    registered = registry.register(descriptor)

    assert registered.name == "demo.plugin"
    assert registry.find_by_capability("demo.answer")[0].name == "demo.plugin"
