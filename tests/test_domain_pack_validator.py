import json

import pytest

from aca_os.component_registry import ComponentRegistry
from aca_os.domain_pack_loader import DomainPackLoader
from aca_os.domain_pack_manifest import DomainPackManifest
from aca_os.domain_pack_validator import (
    DOMAIN_PACK_VALIDATOR_CONTRACT,
    DomainPackValidationStatus,
    DomainPackValidator,
)


def _payload(**overrides):
    payload = {
        "manifest_version": "1",
        "name": "demo.claims",
        "version": "0.1.0",
        "domain": "insurance.claims",
        "description": "Demo deterministic claims domain pack",
        "provider": "aca-labs",
        "runtime": {"min_version": "0.3.0", "max_version": "0.4.0"},
        "capabilities": ["domain.policy.context"],
        "assets": [
            {"name": "concepts", "kind": "concepts", "path": "concepts.json", "format": "json"},
            {"name": "policies", "kind": "policies", "path": "policies", "format": "json-dir"},
            {"name": "notes", "kind": "notes", "path": "notes.md", "format": "md", "required": False},
        ],
        "dependencies": [],
        "tags": ["example"],
        "metadata": {"test": True},
    }
    payload.update(overrides)
    return payload


def _write_pack(root, payload=None, *, concepts='{"claim": true}'):
    root.mkdir(parents=True, exist_ok=True)
    (root / "policies").mkdir(exist_ok=True)
    (root / "concepts.json").write_text(concepts, encoding="utf-8")
    path = root / "domain_pack.json"
    path.write_text(json.dumps(payload or _payload()), encoding="utf-8")
    return path


def test_domain_pack_validator_accepts_valid_manifest_file(tmp_path):
    manifest_path = _write_pack(tmp_path / "demo")
    validator = DomainPackValidator(runtime_version="0.3.0")

    result = validator.validate_manifest_file(manifest_path)

    assert result.valid is True
    assert result.status == DomainPackValidationStatus.VALID
    assert result.manifest.name == "demo.claims"
    assert result.metadata["validator_contract"] == DOMAIN_PACK_VALIDATOR_CONTRACT
    assert result.metadata["domain_code_imported"] is False


def test_domain_pack_validator_reports_manifest_parse_errors(tmp_path):
    path = tmp_path / "domain_pack.json"
    path.write_text("{nope", encoding="utf-8")

    result = DomainPackValidator().validate_manifest_file(path)

    assert result.valid is False
    assert result.status == DomainPackValidationStatus.INVALID
    assert result.issues[0].code == "manifest.invalid"
    assert "Expecting property name" in result.errors[0]


def test_domain_pack_validator_rejects_runtime_that_is_too_old(tmp_path):
    payload = _payload(runtime={"min_version": "0.4.0"})
    manifest_path = _write_pack(tmp_path / "demo", payload)

    result = DomainPackValidator(runtime_version="0.3.0").validate_manifest_file(manifest_path)

    assert result.valid is False
    assert result.issues[0].code == "runtime.too_old"
    assert "requires ACA Runtime" in result.errors[0]


def test_domain_pack_validator_rejects_runtime_that_is_too_new(tmp_path):
    payload = _payload(runtime={"min_version": "0.2.0", "max_version": "0.2.9"})
    manifest_path = _write_pack(tmp_path / "demo", payload)

    result = DomainPackValidator(runtime_version="0.3.0").validate_manifest_file(manifest_path)

    assert result.valid is False
    assert result.issues[0].code == "runtime.too_new"
    assert "supports ACA Runtime" in result.errors[0]


def test_domain_pack_validator_rejects_missing_required_assets(tmp_path):
    root = tmp_path / "demo"
    root.mkdir()
    path = root / "domain_pack.json"
    path.write_text(json.dumps(_payload()), encoding="utf-8")

    result = DomainPackValidator().validate_manifest_file(path)

    assert result.valid is False
    assert {issue.code for issue in result.issues} == {"asset.missing_required"}
    assert "concepts.json" in "; ".join(result.errors)
    assert "policies" in "; ".join(result.errors)


def test_domain_pack_validator_rejects_unsupported_asset_format(tmp_path):
    payload = _payload(
        assets=[
            {"name": "concepts", "kind": "concepts", "path": "concepts.json", "format": "sqlite"},
        ]
    )
    manifest_path = _write_pack(tmp_path / "demo", payload)

    result = DomainPackValidator().validate_manifest_file(manifest_path)

    assert result.valid is False
    assert result.issues[0].code == "asset.unsupported_format"
    assert "sqlite" in result.errors[0]


def test_domain_pack_validator_checks_json_asset_content(tmp_path):
    manifest_path = _write_pack(tmp_path / "demo", concepts="{bad json")

    result = DomainPackValidator().validate_manifest_file(manifest_path)

    assert result.valid is False
    assert result.issues[0].code == "asset.invalid_json"
    assert "Invalid JSON" in result.errors[0]


def test_domain_pack_validator_rejects_self_duplicate_and_blank_dependencies(tmp_path):
    payload = _payload(dependencies=["demo.claims", "", "policy_manager", "policy_manager"])
    manifest_path = _write_pack(tmp_path / "demo", payload)

    result = DomainPackValidator().validate_manifest_file(manifest_path)

    assert result.valid is False
    assert {issue.code for issue in result.issues} == {
        "dependency.self",
        "dependency.blank",
        "dependency.duplicate",
    }


def test_domain_pack_validator_exports_observable_snapshot(tmp_path):
    validator = DomainPackValidator()
    validator.validate_manifest_file(_write_pack(tmp_path / "valid"))
    bad_path = tmp_path / "bad" / "domain_pack.json"
    bad_path.parent.mkdir()
    bad_path.write_text(json.dumps(_payload(domain="")), encoding="utf-8")

    validator.validate_manifest_file(bad_path)
    exported = validator.export(format="dict")
    exported_json = json.loads(validator.export(format="json"))

    assert exported["contract"] == DOMAIN_PACK_VALIDATOR_CONTRACT
    assert exported["validation_count"] == 2
    assert exported["valid_count"] == 1
    assert exported["invalid_count"] == 1
    assert exported_json["results"][0]["valid"] is True


def test_domain_pack_loader_uses_validator_before_registering_pack(tmp_path):
    payload = _payload(assets=[{"name": "concepts", "kind": "concepts", "path": "concepts.json", "format": "sqlite"}])
    manifest_path = _write_pack(tmp_path / "demo", payload)
    registry = ComponentRegistry()
    loader = DomainPackLoader(component_registry=registry)

    snapshot = loader.load(manifest_path)

    assert snapshot.failed_count == 1
    assert registry.get("demo.claims") is None
    assert "Domain Pack validation failed" in snapshot.results[0].errors[0]
    assert snapshot.results[0].metadata["validator_contract"] == DOMAIN_PACK_VALIDATOR_CONTRACT


def test_domain_pack_validator_can_require_valid_file(tmp_path):
    manifest_path = _write_pack(tmp_path / "demo")
    validator = DomainPackValidator()

    result = validator.require_valid_file(manifest_path)

    assert result.valid is True

    bad_path = tmp_path / "bad" / "domain_pack.json"
    bad_path.parent.mkdir()
    bad_path.write_text(json.dumps(_payload(domain="")), encoding="utf-8")

    with pytest.raises(ValueError, match="Domain Pack validation failed"):
        validator.require_valid_file(bad_path)


def test_domain_pack_validator_can_validate_manifest_object(tmp_path):
    manifest_path = _write_pack(tmp_path / "demo")
    manifest = DomainPackManifest.from_file(manifest_path)

    result = DomainPackValidator().validate_manifest(manifest, pack_root=manifest_path.parent)

    assert result.valid is True
    assert result.manifest.name == manifest.name


def test_runtime_registers_domain_pack_validator_boundary():
    from aca_kernel.compiler.compiler import GraphCompiler
    from aca_kernel.core.kernel import ACAKernel
    from aca_kernel.plugins.rules.default_registry import build_default_registry
    from aca_os.component_registry import ComponentState
    from aca_os.mission_manager import MissionManager
    from aca_os.runtime import ACAOSRuntime

    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
    )

    descriptor = runtime.component_registry.require("domain_pack_validator")
    exported = runtime.export_domain_pack_validation()

    assert descriptor.state == ComponentState.ACTIVE
    assert "domain_pack.validate" in descriptor.capabilities
    assert exported["contract"] == DOMAIN_PACK_VALIDATOR_CONTRACT
