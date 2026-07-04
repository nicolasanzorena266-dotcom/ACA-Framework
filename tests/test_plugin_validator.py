import json
from pathlib import Path

import pytest

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.component_registry import ComponentRegistry
from aca_os.mission_manager import MissionManager
from aca_os.plugin_loader import PluginLoadStatus, PluginLoader
from aca_os.plugin_validator import PluginValidator, PluginValidationSeverity
from aca_os.runtime import ACAOSRuntime


def _payload(**overrides):
    payload = {
        "manifest_version": "1",
        "name": "demo.plugin",
        "version": "0.1.0",
        "provider": "aca-labs",
        "runtime": {"min_version": "0.3.0", "max_version": "0.4.0"},
        "entrypoint": {"module": "demo_plugin.main", "factory": "create_plugin"},
        "capabilities": [{"name": "demo.answer", "kind": "tool"}],
        "permissions": [{"name": "trace.read", "reason": "Read execution trace"}],
        "hooks": [{"name": "on_register", "target": "demo_plugin.hooks:on_register"}],
        "dependencies": [],
        "tags": ["example"],
        "metadata": {"test": True},
    }
    payload.update(overrides)
    return payload


def _write_manifest(root: Path, payload: dict):
    root.mkdir(parents=True, exist_ok=True)
    path = root / "plugin.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_plugin_validator_accepts_safe_manifest_contract():
    report = PluginValidator().validate(_payload())

    assert report.valid is True
    assert report.error_count == 0
    assert report.manifest.name == "demo.plugin"
    assert report.metadata["runtime_version"] == "0.3.0"


def test_plugin_validator_reports_manifest_parse_errors(tmp_path):
    path = _write_manifest(tmp_path / "bad", _payload())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("entrypoint")
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = PluginValidator().validate(path)

    assert report.valid is False
    assert report.error_count == 1
    assert report.issues[0].code == "manifest.invalid"
    assert "entrypoint" in report.issues[0].message


def test_plugin_validator_rejects_runtime_version_incompatibility():
    report = PluginValidator(runtime_version="0.3.0").validate(
        _payload(runtime={"min_version": "0.4.0"})
    )

    assert report.valid is False
    assert report.issues[0].code == "runtime.version.too_low"


def test_plugin_validator_rejects_unsafe_entrypoint_paths():
    report = PluginValidator().validate(
        _payload(entrypoint={"module": "../bad/path", "factory": "create-plugin"})
    )

    assert report.valid is False
    codes = {issue.code for issue in report.issues}
    assert "entrypoint.module.invalid" in codes
    assert "entrypoint.factory.invalid" in codes


def test_plugin_validator_rejects_permissions_outside_runtime_allowlist():
    report = PluginValidator().validate(_payload(permissions=["network.raw"] ))

    assert report.valid is False
    assert report.issues[0].code == "permission.not_allowed"


def test_plugin_validator_warns_when_permission_reason_is_missing():
    report = PluginValidator().validate(_payload(permissions=["trace.read"]))

    assert report.valid is True
    assert report.warning_count == 1
    assert report.issues[0].severity == PluginValidationSeverity.WARNING


def test_plugin_validator_rejects_missing_registry_dependencies():
    registry = ComponentRegistry()
    report = PluginValidator(component_registry=registry).validate(
        _payload(dependencies=["metrics_engine"])
    )

    assert report.valid is False
    assert report.issues[0].code == "dependency.missing"
    assert "metrics_engine" in report.issues[0].message


def test_plugin_loader_uses_validator_before_component_registration(tmp_path):
    path = _write_manifest(tmp_path / "unsafe", _payload(permissions=["network.raw"]))
    registry = ComponentRegistry()
    loader = PluginLoader(component_registry=registry)

    snapshot = loader.load(path)

    assert snapshot.failed_count == 1
    assert snapshot.results[0].status == PluginLoadStatus.FAILED
    assert registry.get("demo.plugin") is None
    assert "permission" in snapshot.results[0].errors[0]


def test_runtime_exposes_plugin_validation_boundary():
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    report = runtime.validate_plugin(_payload())

    assert report["valid"] is True
    assert "plugin_validator" in {item["name"] for item in runtime.export_components()["components"]}


def test_plugin_validator_exports_json_report():
    report = PluginValidator().export_report(_payload(), format="json")

    assert json.loads(report)["contract"] == "plugin_validator.v1"


@pytest.mark.parametrize(
    "hook_target",
    ["missing_separator", "../bad:on_register", "demo.hooks:on-register"],
)
def test_plugin_validator_rejects_unsafe_hook_targets(hook_target):
    report = PluginValidator().validate(
        _payload(hooks=[{"name": "on_register", "target": hook_target}])
    )

    assert report.valid is False
    assert any(issue.code.startswith("hook.target") for issue in report.issues)
