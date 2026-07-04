from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from aca_os.plugin_manifest import PluginManifest
from aca_os.plugin_validator import PluginValidationReport, PluginValidator

PLUGIN_EXAMPLES_CONTRACT = "plugin_examples.v1"
DEFAULT_EXAMPLES_ROOT = Path("examples/plugins")


@dataclass(frozen=True)
class ExamplePluginDescriptor:
    """Read-only descriptor for a repository-hosted example plugin.

    Example plugins are part of the SDK contract documentation. This descriptor
    exposes their manifests to tests, docs, Studio and future CLI commands
    without importing plugin entrypoints.
    """

    name: str
    version: str
    manifest_path: str
    plugin_root: str
    description: str = ""
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    permissions: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "manifest_path": self.manifest_path,
            "plugin_root": self.plugin_root,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "permissions": list(self.permissions),
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ExamplePluginCatalog:
    contract: str
    root: str
    plugin_count: int
    plugins: tuple[ExamplePluginDescriptor, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "root": self.root,
            "plugin_count": self.plugin_count,
            "plugins": [plugin.to_dict() for plugin in self.plugins],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class ExamplePluginValidationSnapshot:
    contract: str
    root: str
    plugin_count: int
    valid_count: int
    invalid_count: int
    reports: tuple[PluginValidationReport, ...] = field(default_factory=tuple)

    @property
    def valid(self) -> bool:
        return self.invalid_count == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "root": self.root,
            "plugin_count": self.plugin_count,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "valid": self.valid,
            "reports": [report.to_dict() for report in self.reports],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def list_example_manifests(root: str | Path = DEFAULT_EXAMPLES_ROOT) -> tuple[Path, ...]:
    base = Path(root)
    if not base.exists():
        raise FileNotFoundError(f"Example plugin root does not exist: {base}")
    return tuple(sorted(base.rglob("plugin.json"), key=lambda path: path.as_posix()))


def build_example_catalog(root: str | Path = DEFAULT_EXAMPLES_ROOT) -> ExamplePluginCatalog:
    base = Path(root)
    plugins = tuple(_descriptor_from_manifest(path) for path in list_example_manifests(base))
    return ExamplePluginCatalog(
        contract=PLUGIN_EXAMPLES_CONTRACT,
        root=base.as_posix(),
        plugin_count=len(plugins),
        plugins=plugins,
    )


def validate_example_plugins(
    root: str | Path = DEFAULT_EXAMPLES_ROOT,
    *,
    validator: PluginValidator | None = None,
) -> ExamplePluginValidationSnapshot:
    base = Path(root)
    plugin_validator = validator or PluginValidator()
    reports = tuple(plugin_validator.validate(path) for path in list_example_manifests(base))
    return ExamplePluginValidationSnapshot(
        contract=PLUGIN_EXAMPLES_CONTRACT,
        root=base.as_posix(),
        plugin_count=len(reports),
        valid_count=sum(1 for report in reports if report.valid),
        invalid_count=sum(1 for report in reports if not report.valid),
        reports=reports,
    )


def export_example_catalog(
    root: str | Path = DEFAULT_EXAMPLES_ROOT,
    *,
    format: str = "dict",
) -> Dict[str, Any] | str:
    catalog = build_example_catalog(root)
    if format == "dict":
        return catalog.to_dict()
    if format == "json":
        return catalog.to_json()
    raise ValueError(f"Unsupported example plugin catalog export format: {format}")


def _descriptor_from_manifest(path: Path) -> ExamplePluginDescriptor:
    manifest = PluginManifest.from_file(path)
    return ExamplePluginDescriptor(
        name=manifest.name,
        version=manifest.version,
        manifest_path=path.as_posix(),
        plugin_root=path.parent.as_posix(),
        description=manifest.description,
        capabilities=tuple(capability.name for capability in manifest.capabilities),
        permissions=tuple(permission.name for permission in manifest.permissions),
        tags=manifest.tags,
        metadata=manifest.metadata,
    )
