from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from aca_os.component_registry import ComponentDescriptor, ComponentState


SUPPORTED_DOMAIN_PACK_MANIFEST_VERSION = "1"


@dataclass(frozen=True)
class DomainPackRuntimeCompatibility:
    """Declared ACA Runtime compatibility for a Domain Pack.

    Sprint 45 defines the manifest boundary only. Domain Packs are structured,
    deterministic domain assets; the parser never imports runtime internals and
    never executes domain code.
    """

    min_version: str = "0.3.0"
    max_version: str | None = None

    def __post_init__(self) -> None:
        if not self.min_version or not self.min_version.strip():
            raise ValueError("Domain Pack runtime.min_version is required.")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "DomainPackRuntimeCompatibility":
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
class DomainPackCapability:
    """Runtime-visible capability exposed by a Domain Pack."""

    name: str
    kind: str = "domain"
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Domain Pack capability name is required.")
        if not self.kind or not self.kind.strip():
            raise ValueError("Domain Pack capability kind is required.")

    @classmethod
    def from_value(cls, value: str | Mapping[str, Any]) -> "DomainPackCapability":
        if isinstance(value, str):
            return cls(name=value)
        return cls(
            name=str(value.get("name", "")),
            kind=str(value.get("kind", "domain")),
            description=str(value.get("description", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "description": self.description,
        }


@dataclass(frozen=True)
class DomainPackAsset:
    """Structured asset declared by a Domain Pack manifest.

    Assets are data references only. They identify concepts, policies, scenarios,
    prompts, lexicons or examples without loading them at manifest-parse time.
    """

    name: str
    kind: str
    path: str
    format: str = "json"
    description: str = ""
    required: bool = True

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Domain Pack asset name is required.")
        if not self.kind or not self.kind.strip():
            raise ValueError("Domain Pack asset kind is required.")
        if not self.path or not self.path.strip():
            raise ValueError("Domain Pack asset path is required.")
        if self.path.startswith("/") or ".." in Path(self.path).parts:
            raise ValueError(f"Domain Pack asset path must be relative and safe: {self.path}")
        if not self.format or not self.format.strip():
            raise ValueError("Domain Pack asset format is required.")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DomainPackAsset":
        return cls(
            name=str(data.get("name", "")),
            kind=str(data.get("kind", "")),
            path=str(data.get("path", "")),
            format=str(data.get("format", "json")),
            description=str(data.get("description", "")),
            required=bool(data.get("required", True)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "path": self.path,
            "format": self.format,
            "description": self.description,
            "required": self.required,
        }


@dataclass(frozen=True)
class DomainPackManifest:
    """Stable Domain Pack manifest contract.

    Domain Packs give ACA domain vocabulary and policy context without coupling
    packs to Runtime internals. The manifest is the only runtime-facing boundary
    Sprint 45 introduces.
    """

    name: str
    version: str
    domain: str
    manifest_version: str = SUPPORTED_DOMAIN_PACK_MANIFEST_VERSION
    description: str = ""
    provider: str = "external"
    runtime: DomainPackRuntimeCompatibility = field(default_factory=DomainPackRuntimeCompatibility)
    capabilities: tuple[DomainPackCapability, ...] = field(default_factory=tuple)
    assets: tuple[DomainPackAsset, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Domain Pack name is required.")
        if not self.version or not self.version.strip():
            raise ValueError("Domain Pack version is required.")
        if not self.domain or not self.domain.strip():
            raise ValueError("Domain Pack domain is required.")
        if self.manifest_version != SUPPORTED_DOMAIN_PACK_MANIFEST_VERSION:
            raise ValueError(
                f"Unsupported domain pack manifest version: {self.manifest_version}. "
                f"Supported version: {SUPPORTED_DOMAIN_PACK_MANIFEST_VERSION}."
            )
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "assets", tuple(self.assets))
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "tags", tuple(self.tags))
        _ensure_unique("Domain Pack capability", [item.name for item in self.capabilities])
        _ensure_unique("Domain Pack asset", [item.name for item in self.assets])

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DomainPackManifest":
        values = dict(data)
        return cls(
            manifest_version=str(values.get("manifest_version", SUPPORTED_DOMAIN_PACK_MANIFEST_VERSION)),
            name=str(values.get("name", "")),
            version=str(values.get("version", "")),
            domain=str(values.get("domain", "")),
            description=str(values.get("description", "")),
            provider=str(values.get("provider", "external")),
            runtime=DomainPackRuntimeCompatibility.from_dict(values.get("runtime")),
            capabilities=tuple(
                DomainPackCapability.from_value(item) for item in values.get("capabilities", [])
            ),
            assets=tuple(DomainPackAsset.from_dict(item) for item in values.get("assets", [])),
            dependencies=tuple(str(item) for item in values.get("dependencies", [])),
            tags=tuple(str(item) for item in values.get("tags", [])),
            metadata=values.get("metadata", {}) or {},
        )

    @classmethod
    def from_json(cls, payload: str) -> "DomainPackManifest":
        return cls.from_dict(json.loads(payload))

    @classmethod
    def from_file(cls, path: str | Path) -> "DomainPackManifest":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "name": self.name,
            "version": self.version,
            "domain": self.domain,
            "description": self.description,
            "provider": self.provider,
            "runtime": self.runtime.to_dict(),
            "capabilities": [item.to_dict() for item in self.capabilities],
            "assets": [item.to_dict() for item in self.assets],
            "dependencies": list(self.dependencies),
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def capability_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.capabilities)

    def asset_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self.assets)

    def asset_paths(self) -> tuple[str, ...]:
        return tuple(item.path for item in self.assets)

    def to_component_descriptor(
        self,
        *,
        state: ComponentState | str = ComponentState.REGISTERED,
    ) -> ComponentDescriptor:
        return ComponentDescriptor(
            name=self.name,
            class_name="DomainPackManifest",
            role="domain_pack",
            version=self.version,
            provider=self.provider,
            capabilities=self.capability_names(),
            dependencies=self.dependencies,
            tags=("domain-pack", self.domain, *self.tags),
            state=ComponentState(state),
            metadata={
                "manifest_version": self.manifest_version,
                "description": self.description,
                "domain": self.domain,
                "runtime": self.runtime.to_dict(),
                "assets": [item.to_dict() for item in self.assets],
                "domain_pack_metadata": dict(self.metadata),
            },
        )


@dataclass(frozen=True)
class DomainPackContract:
    """Runtime-facing contract produced from a Domain Pack manifest."""

    manifest: DomainPackManifest
    component: ComponentDescriptor

    @classmethod
    def from_manifest(cls, manifest: DomainPackManifest) -> "DomainPackContract":
        return cls(manifest=manifest, component=manifest.to_component_descriptor())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest": self.manifest.to_dict(),
            "component": self.component.to_dict(),
        }


def build_domain_pack_contract(data: Mapping[str, Any] | DomainPackManifest) -> DomainPackContract:
    manifest = data if isinstance(data, DomainPackManifest) else DomainPackManifest.from_dict(data)
    return DomainPackContract.from_manifest(manifest)


def _ensure_unique(label: str, values: Iterable[str]) -> None:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen:
            duplicates.append(value)
        seen.add(value)
    if duplicates:
        raise ValueError(f"{label} names must be unique: {', '.join(sorted(set(duplicates)))}")
