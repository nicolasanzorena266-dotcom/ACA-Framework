import sys
from pathlib import Path

from aca_os.component_registry import ComponentRegistry
from aca_os.plugin_examples import (
    PLUGIN_EXAMPLES_CONTRACT,
    build_example_catalog,
    export_example_catalog,
    list_example_manifests,
    validate_example_plugins,
)
from aca_os.plugin_lifecycle import PluginLifecycleManager, PluginLifecycleState
from aca_os.plugin_loader import PluginLoadStatus, PluginLoader
from aca_os.plugin_validator import PluginValidator

EXAMPLES_ROOT = Path("examples/plugins")
ENTRYPOINT_MODULES = {
    "examples.plugins.echo_tool.plugin",
    "examples.plugins.context_snapshot.plugin",
    "examples.plugins.decision_audit.plugin",
}


def test_example_plugin_catalog_lists_reference_plugins():
    catalog = build_example_catalog(EXAMPLES_ROOT)

    assert catalog.contract == PLUGIN_EXAMPLES_CONTRACT
    assert catalog.plugin_count == 3
    assert [plugin.name for plugin in catalog.plugins] == [
        "example.context_snapshot",
        "example.decision_audit",
        "example.echo_tool",
    ]
    assert all(plugin.metadata["example"] is True for plugin in catalog.plugins)


def test_example_plugin_catalog_exports_json():
    payload = export_example_catalog(EXAMPLES_ROOT, format="json")

    assert '"contract": "plugin_examples.v1"' in payload
    assert '"plugin_count": 3' in payload
    assert "example.echo_tool" in payload


def test_example_plugin_manifests_validate_without_registry_side_effects():
    snapshot = validate_example_plugins(EXAMPLES_ROOT, validator=PluginValidator())

    assert snapshot.valid is True
    assert snapshot.plugin_count == 3
    assert snapshot.valid_count == 3
    assert snapshot.invalid_count == 0
    assert all(report.error_count == 0 for report in snapshot.reports)


def test_example_plugins_load_as_metadata_only():
    before = {name for name in ENTRYPOINT_MODULES if name in sys.modules}
    registry = ComponentRegistry()
    loader = PluginLoader(component_registry=registry)

    snapshot = loader.load(EXAMPLES_ROOT)

    assert snapshot.loaded_count == 3
    assert snapshot.failed_count == 0
    assert snapshot.skipped_count == 0
    assert {result.status for result in snapshot.results} == {PluginLoadStatus.LOADED}
    assert registry.find_by_capability("tool.echo")[0].name == "example.echo_tool"
    assert registry.find_by_capability("context.snapshot")[0].name == "example.context_snapshot"
    assert registry.find_by_capability("decision.audit")[0].name == "example.decision_audit"
    assert {name for name in ENTRYPOINT_MODULES if name in sys.modules} == before


def test_example_plugins_attach_to_lifecycle_and_transition():
    registry = ComponentRegistry()
    loader = PluginLoader(component_registry=registry)
    lifecycle = PluginLifecycleManager(component_registry=registry, plugin_loader=loader)

    load_snapshot = loader.load(EXAMPLES_ROOT)
    records = lifecycle.attach_many(load_snapshot.results)

    assert len(records) == 3
    lifecycle.initialize("example.echo_tool")
    lifecycle.activate("example.echo_tool")
    lifecycle.pause("example.echo_tool")
    lifecycle.stop("example.echo_tool")

    snapshot = lifecycle.snapshot()
    echo = lifecycle.require("example.echo_tool")
    assert echo.state == PluginLifecycleState.STOPPED
    assert snapshot.plugin_count == 3
    assert snapshot.states["registered"] == 2
    assert snapshot.states["stopped"] == 1


def test_example_manifest_discovery_is_deterministic():
    manifests = list_example_manifests(EXAMPLES_ROOT)

    assert [path.as_posix() for path in manifests] == sorted(path.as_posix() for path in manifests)
    assert all(path.name == "plugin.json" for path in manifests)
