import json

import pytest

from aca_os.component_registry import ComponentRegistry, ComponentState
from aca_os.domain_pack_manifest import (
    DomainPackContract,
    DomainPackManifest,
    SUPPORTED_DOMAIN_PACK_MANIFEST_VERSION,
    build_domain_pack_contract,
)


def _manifest_payload():
    return {
        "manifest_version": SUPPORTED_DOMAIN_PACK_MANIFEST_VERSION,
        "name": "galicia.siniestros",
        "version": "0.1.0",
        "domain": "insurance.auto_claims",
        "description": "Galicia siniestros informational domain vocabulary",
        "provider": "aca-labs",
        "runtime": {"min_version": "0.3.0", "max_version": "0.4.0"},
        "capabilities": [
            {
                "name": "domain.concepts.lookup",
                "kind": "knowledge",
                "description": "Expose structured claim concepts",
            },
            "domain.policy.context",
        ],
        "assets": [
            {
                "name": "concepts",
                "kind": "concepts",
                "path": "concepts",
                "format": "json-dir",
                "description": "Domain concept cards",
            },
            {
                "name": "policies",
                "kind": "policies",
                "path": "policies",
                "format": "json-dir",
            },
            {
                "name": "scenarios",
                "kind": "scenarios",
                "path": "scenarios",
                "format": "json-dir",
                "required": False,
            },
        ],
        "dependencies": ["policy_manager"],
        "tags": ["example", "insurance"],
        "metadata": {"owner": "tests"},
    }


def test_domain_pack_manifest_parses_contract_metadata():
    manifest = DomainPackManifest.from_dict(_manifest_payload())

    assert manifest.name == "galicia.siniestros"
    assert manifest.domain == "insurance.auto_claims"
    assert manifest.capability_names() == ("domain.concepts.lookup", "domain.policy.context")
    assert manifest.asset_names() == ("concepts", "policies", "scenarios")
    assert manifest.asset_paths() == ("concepts", "policies", "scenarios")
    assert manifest.runtime.min_version == "0.3.0"


def test_domain_pack_manifest_round_trips_json_deterministically():
    manifest = DomainPackManifest.from_dict(_manifest_payload())
    restored = DomainPackManifest.from_json(manifest.to_json())

    assert restored.to_dict() == manifest.to_dict()
    assert json.loads(restored.to_json())["domain"] == "insurance.auto_claims"


def test_domain_pack_manifest_can_load_from_file(tmp_path):
    path = tmp_path / "domain_pack.json"
    path.write_text(json.dumps(_manifest_payload()), encoding="utf-8")

    manifest = DomainPackManifest.from_file(path)

    assert manifest.name == "galicia.siniestros"
    assert manifest.asset_names()[0] == "concepts"


def test_domain_pack_manifest_rejects_invalid_manifest_version():
    payload = _manifest_payload()
    payload["manifest_version"] = "99"

    with pytest.raises(ValueError, match="Unsupported domain pack manifest version"):
        DomainPackManifest.from_dict(payload)


def test_domain_pack_manifest_requires_domain_identity():
    payload = _manifest_payload()
    payload["domain"] = ""

    with pytest.raises(ValueError, match="domain"):
        DomainPackManifest.from_dict(payload)


def test_domain_pack_manifest_rejects_duplicate_assets_and_capabilities():
    payload = _manifest_payload()
    payload["assets"] = [payload["assets"][0], payload["assets"][0]]

    with pytest.raises(ValueError, match="asset"):
        DomainPackManifest.from_dict(payload)

    payload = _manifest_payload()
    payload["capabilities"] = ["domain.policy.context", "domain.policy.context"]

    with pytest.raises(ValueError, match="capability"):
        DomainPackManifest.from_dict(payload)


def test_domain_pack_manifest_rejects_unsafe_asset_paths():
    payload = _manifest_payload()
    payload["assets"][0]["path"] = "../secrets"

    with pytest.raises(ValueError, match="relative and safe"):
        DomainPackManifest.from_dict(payload)


def test_domain_pack_contract_projects_to_component_descriptor():
    contract = build_domain_pack_contract(_manifest_payload())
    component = contract.component

    assert isinstance(contract, DomainPackContract)
    assert component.name == "galicia.siniestros"
    assert component.role == "domain_pack"
    assert component.class_name == "DomainPackManifest"
    assert component.state == ComponentState.REGISTERED
    assert "domain.concepts.lookup" in component.capabilities
    assert "domain-pack" in component.tags
    assert "insurance.auto_claims" in component.tags
    assert component.metadata["assets"][0]["path"] == "concepts"


def test_domain_pack_descriptor_can_enter_component_registry_after_dependencies_exist():
    registry = ComponentRegistry()
    registry.register_instance(
        name="policy_manager",
        instance=object(),
        role="runtime policy manager",
        capabilities=("policy.evaluate",),
    )

    descriptor = DomainPackManifest.from_dict(_manifest_payload()).to_component_descriptor()
    registered = registry.register(descriptor)

    assert registered.name == "galicia.siniestros"
    assert registry.find_by_capability("domain.policy.context")[0].name == "galicia.siniestros"
