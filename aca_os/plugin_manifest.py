from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from aca_os.component_registry import ComponentDescriptor, ComponentState


SUPPORTED_MANIFEST_VERSION = "1"


@dataclass(frozen=True)
class RuntimeCompatibility:
    """Declared ACA Runtime compatibility for a plugin.

    This is a contract only. Sprint 35 deliberately does not load or execute
    plugins; it defines the deterministic metadata boundary future loaders must
    validate before any code is touched.
    """

    min_version: str = "0.3.0"
    max_version: str | None = None

    def __post_init__(self) -> None:
        if not self.min_version or not self.min_version.strip():
            raise ValueError("Plugin runtime.min_version is required.")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "RuntimeCompatibility":
        values = dict(data or {})
        return cls(
            min_version=str(values.get("min_version", "0.3.0")),
            max_version=values.get("max_version"),
        )

    def to_dict(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {"min_version": self.min_version}
        if self.max_version is not None:
            output["max_version"] = self.max_version
        return output


@dataclass(frozen=True)
class PluginCapability:
    """Runtime-visible capability exposed by a plugin manifest."""

    name: str
    kind: str = "runtime"
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Plugin capability name is required.")
        if not self.kind or not self.kind.strip():
            raise ValueError("Plugin capability kind is required.")

    @classmethod
    def from_value(cls, value: str | Mapping[str, Any]) -> "PluginCapability":
        if isinstance(value, str):
            return cls(name=value)
        return cls(
            name=str(value.get("name", "")),
            kind=str(value.get("kind", "runtime")),
            description=str(value.get("description", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
        }


@dataclass(frozen=True)
class PluginPermission:
    """Permission declared by a plugin before it can be loaded."""

    name: str
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Plugin permission name is required.")

    @classmethod
    def from_value(cls, value: str | Mapping[str, Any]) -> "PluginPermission":
        if isinstance(value, str):
            return cls(name=value)
        return cls(name=str(value.get("name", "")), reason=str(value.get("reason", "")))

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "reason": self.reason}


@dataclass(frozen=True)
class PluginHook:
    """Lifecycle hook declared by a plugin manifest."""

    name: str
    target: str

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Plugin hook name is required.")
        if not self.target or not self.target.strip():
            raise ValueError("Plugin hook target is required.")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PluginHook":
        return cls(name=str(data.get("name", "")), target=str(data.get("target", "")))

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "target": self.target}


@dataclass(frozen=True)
class PluginEntrypoint:
    """Import boundary declared by a plugin.

    It is intentionally represented as data. The manifest parser never imports
    this target; future loader stages will decide whether and how to execute it.
    """

    module: str
    factory: str = "create_plugin"

    def __post_init__(self) -> None:
        if not self.module or not self.module.strip():
            raise ValueError("Plugin entrypoint.module is required.")
        if not self.factory or not self.factory.strip():
            raise ValueError("Plugin entrypoint.factory is required.")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PluginEntrypoint":
        return cls(
            module=str(data.get("module", "")),
            factory=str(data.get("factory", "create_plugin")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {"module": self.module, "factory": self.factory}


@dataclass(frozen=True)
class PluginManifest:
    """Stable Plugin SDK manifest contract.

    Sprint 35 defines the first plugin boundary for ACA. A plugin is visible to
    the Runtime through this manifest before any implementation can be loaded.
    """

    name: str
    version: str
    entrypoint: PluginEntrypoint
    manifest_version: str = SUPPORTED_MANIFEST_VERSION
    description: str = ""
    provider: str = "external"
    runtime: RuntimeCompatibility = field(default_factory=RuntimeCompatibility)
    capabilities: tuple[PluginCapability, ...] = field(default_factory=tuple)
    permissions: tuple[PluginPermission, ...] = field(default_factory=tuple)
    hooks: tuple[PluginHook, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Plugin name is required.")
        if not self.version or not self.version.strip():
            raise ValueError("Plugin version is required.")
        if self.manifest_version != SUPPORTED_MANIFEST_VERSION:
            raise ValueError(
                f"Unsupported plugin manifest version: {self.manifest_version}. "
                f"Supported version: {SUPPORTED_MANIFEST_VERSION}."
            )
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "permissions", tuple(self.permissions))
        object.__setattr__(self, "hooks", tuple(self.hooks))
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "tags", tuple(self.tags))
        _ensure_unique("Plugin capability", [item.name for item in self.capabilities])
        _ensure_unique("Plugin permission", [item.name for item in self.permissions])
        _ensure_unique("Plugin hook", [item.name for item in self.hooks])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PluginManifest":
        values = dict(data)
        if "entrypoint" not in values:
            raise ValueError("Plugin entrypoint is required.")
        return cls(
            manifest_version=str(values.get("manifest_version", SUPPORTED_MANIFEST_VERSION)),
            name=str(values.get("name", "")),
            version=str(values.get("version", "")),
            description=str(values.get("description", "")),
            provider=str(values.get("provider", "external")),
            runtime=RuntimeCompatibility.from_dict(values.get("runtime")),
            entrypoint=PluginEntrypoint.from_dict(values.get("entrypoint") or {}),
            capabilities=tuple(
                PluginCapability.from_value(item) for item in values.get("capabilities", [])
            ),
            permissions=tuple(
                PluginPermission.from_value(item) for item in values.get("permissions", [])
            ),
            hooks=tuple(PluginHook.from_dict(item) for item in values.get("hooks", [])),
            dependencies=tuple(str(item) for item in values.get("dependencies", [])),
            tags=tuple(str(item) for item in values.get("tags", [])),
            metadata=values.get("metadata", {}) or {},
        )

    @classmethod
    def from_json(cls, payload: str) -> "PluginManifest":
        return cls.from_dict(json.loads(payload))

    @classmethod
    def from_file(cls, path: str | Path) -> "PluginManifest":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "provider": self.provider,
            "runtime": self.runtime.to_dict(),
            "entrypoint": self.entrypoint.to_dict(),
            "capabilities": [item.to_dict() for item in self.capabilities],
            "permissions": [item.to_dict() for item in self.permissions],
            "hooks": [item.to_dict() for item in self.hooks],
            "dependencies": list(self.dependencies),
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def capability_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.capabilities)

    def permission_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.permissions)

    def hook_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.hooks)

    def to_component_descriptor(
        self,
        *,
        state: ComponentState | str = ComponentState.REGISTERED,
    ) -> ComponentDescriptor:
        return ComponentDescriptor(
            name=self.name,
            class_name="PluginManifest",
            role="plugin",
            version=self.version,
            provider=self.provider,
            capabilities=self.capability_names(),
            dependencies=self.dependencies,
            tags=("plugin", *self.tags),
            state=ComponentState(state),
            metadata={
                "manifest_version": self.manifest_version,
                "description": self.description,
                "entrypoint": self.entrypoint.to_dict(),
                "runtime": self.runtime.to_dict(),
                "permissions": [item.to_dict() for item in self.permissions],
                "hooks": [item.to_dict() for item in self.hooks],
                "plugin_metadata": dict(self.metadata),
            },
        )


@dataclass(frozen=True)
class PluginContract:
    """Validated runtime-facing contract produced from a manifest."""

    manifest: PluginManifest
    component: ComponentDescriptor

    @classmethod
    def from_manifest(cls, manifest: PluginManifest) -> "PluginContract":
        return cls(manifest=manifest, component=manifest.to_component_descriptor())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "component": self.component.to_dict(),
        }


def build_plugin_contract(data: Mapping[str, Any] | PluginManifest) -> PluginContract:
    manifest = data if isinstance(data, PluginManifest) else PluginManifest.from_dict(data)
    return PluginContract.from_manifest(manifest)


def _ensure_unique(label: str, values: Iterable[str]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen:
            duplicates.append(value)
        seen.add(value)
    if duplicates:
        raise ValueError(f"{label} names must be unique: {', '.join(sorted(set(duplicates)))}")
