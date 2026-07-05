from __future__ import annotations

import shutil
from pathlib import Path

from aca_core import (
    CapabilityRegistry,
    CorePolicy,
    DomainPolicy,
    PluginLoader,
    PluginManifest,
    PluginRegistry,
    PluginRuntime,
)

PROHIBITED_CORE_TERMS = (
    "galicia",
    "cristales",
    "siniestro",
    "telecom",
    "pickit",
    "facturacion",
    "paquete",
    "denuncia",
)


def _copy_plugin(source_name: str, target_root: Path) -> Path:
    source = Path("plugins") / source_name
    target = target_root / source_name
    shutil.copytree(source, target)
    return target


def _write_mock_hospital_plugin(root: Path) -> Path:
    plugin_dir = root / "mock.hospital"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "manifest.yaml").write_text(
        """
api_version: 1

plugin:
  id: mock.hospital
  type: domain
  version: 1.0.0
  display_name: Mock Hospital

requires:
  aca_core: ">=0.4.0"
  aca_plugin_sdk: "^1.0.0"

exports:
  semantic: false
  planner: false
  policy: false
  prompts: false
  knowledge: false
  tools: false
  evals: true
  traces: true
  assets: false

handles:
  - health.triage
  - health.appointments

blocked_capabilities:
  - health.patient_record.lookup
""".strip(),
        encoding="utf-8",
    )
    return plugin_dir


def test_specialized_plugin_can_be_removed_without_breaking_core(tmp_path: Path) -> None:
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()
    _copy_plugin("generic.open_chat", plugins_root)

    runtime = PluginRuntime.from_path(plugins_root)
    result = runtime.process("hola", conversation_id="c1")

    assert result.route.selected_plugin_id == "generic.open_chat"
    assert result.route.selected_capability == "generic.open_chat"
    assert "galicia.insurance" not in runtime.plugin_registry.plugin_ids()
    assert result.state is not None
    assert result.state.plugin_id == "generic.open_chat"


def test_mock_plugin_is_detected_without_core_changes(tmp_path: Path) -> None:
    plugins_root = tmp_path / "plugins"
    plugins_root.mkdir()
    _copy_plugin("generic.open_chat", plugins_root)
    _write_mock_hospital_plugin(plugins_root)

    loader = PluginLoader(plugins_root)
    registry = loader.load_registry()
    capabilities = CapabilityRegistry.from_plugins(registry)

    assert "mock.hospital" in registry.plugin_ids()
    assert capabilities.providers_for("health.triage") == ("mock.hospital",)

    runtime = PluginRuntime(registry, capabilities)
    result = runtime.process("hospital triage", conversation_id="case-7")

    assert result.route.selected_plugin_id == "mock.hospital"
    assert result.route.selected_capability == "health.triage"
    assert result.state is not None
    assert result.state.key == "case-7:mock.hospital:health.triage"
    assert result.trace["active_plugin_id"] == "mock.hospital"
    assert result.trace["active_capability"] == "health.triage"


def test_manifest_schema_validates_versioned_plugin_contract() -> None:
    manifest = PluginManifest.from_file("plugins/galicia.insurance/manifest.yaml")

    assert manifest.api_version == 1
    assert manifest.id == "galicia.insurance"
    assert manifest.plugin.type == "domain"
    assert manifest.requires.aca_core == ">=0.4.0"
    assert manifest.requires.aca_plugin_sdk == "^1.0.0"
    assert manifest.exports.semantic is True
    assert "insurance.claims" in manifest.handles
    assert "insurance.document.upload" in manifest.blocked_capabilities


def test_core_policy_is_separate_from_domain_policy() -> None:
    manifest = PluginManifest.from_file("plugins/galicia.insurance/manifest.yaml")
    core_policy = CorePolicy()
    domain_policy = DomainPolicy.from_manifest(manifest)

    assert core_policy.fallback_capability == "generic.open_chat"
    assert domain_policy.plugin_id == "galicia.insurance"
    assert domain_policy.allows("insurance.claims") is True
    assert domain_policy.allows("insurance.claim_status.lookup") is False
    assert "insurance.claim_status.lookup" not in core_policy.to_dict().values()


def test_business_terms_do_not_leak_into_aca_core_source() -> None:
    scanned_files = list(Path("aca_core").rglob("*.py"))
    assert scanned_files
    for path in scanned_files:
        text = path.read_text(encoding="utf-8").lower()
        leaked = [term for term in PROHIBITED_CORE_TERMS if term in text]
        assert leaked == [], f"{path} leaks business terms: {leaked}"
