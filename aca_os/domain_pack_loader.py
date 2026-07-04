from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from aca_os.component_registry import ComponentDescriptor, ComponentRegistry, ComponentState
from aca_os.domain_pack_manifest import (
    DomainPackContract,
    DomainPackManifest,
    build_domain_pack_contract,
)


DEFAULT_DOMAIN_PACK_MANIFEST = "domain_pack.json"
DOMAIN_PACK_LOADER_CONTRACT = "domain_pack_loader.v1"


class DomainPackLoadStatus(str, Enum):
    DISCOVERED = "discovered"
    LOADED = "loaded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class DomainPackLoadResult:
    """Deterministic result of one Domain Pack load attempt.

    Sprint 46 loads manifest metadata and checks declared required assets. It
    never imports Domain Pack code and never lets packs reach runtime internals.
    Runtime visibility is achieved only through ComponentRegistry descriptors.
    """

    status: DomainPackLoadStatus
    manifest_path: str
    pack_root: str
    manifest: DomainPackManifest | None = None
    contract: DomainPackContract | None = None
    component: ComponentDescriptor | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def loaded(self) -> bool:
        return self.status == DomainPackLoadStatus.LOADED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "manifest_path": self.manifest_path,
            "pack_root": self.pack_root,
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "contract": self.contract.to_dict() if self.contract else None,
            "component": self.component.to_dict() if self.component else None,
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DomainPackLoaderSnapshot:
    contract: str
    pack_count: int
    loaded_count: int
    failed_count: int
    skipped_count: int
    results: tuple[DomainPackLoadResult, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "pack_count": self.pack_count,
            "loaded_count": self.loaded_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "results": [result.to_dict() for result in self.results],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class DomainPackLoader:
    """Manifest-first Domain Pack loader.

    Domain Packs are deterministic data bundles. The loader discovers manifests,
    validates the minimal load-time boundary, and registers the resulting domain
    pack descriptors. It deliberately does not import domain_pack.py files.
    """

    def __init__(
        self,
        *,
        manifest_filename: str = DEFAULT_DOMAIN_PACK_MANIFEST,
        component_registry: ComponentRegistry | None = None,
    ) -> None:
        if not manifest_filename or not manifest_filename.strip():
            raise ValueError("Domain Pack manifest filename is required.")
        self.manifest_filename = manifest_filename
        self.component_registry = component_registry
        self._results: List[DomainPackLoadResult] = []

    def bind_registry(self, registry: ComponentRegistry) -> None:
        self.component_registry = registry

    def discover(self, root: str | Path) -> list[Path]:
        base = Path(root)
        if not base.exists():
            raise FileNotFoundError(f"Domain Pack path does not exist: {base}")
        if base.is_file():
            if base.name != self.manifest_filename:
                raise ValueError(
                    f"Expected Domain Pack manifest file named {self.manifest_filename}: {base}"
                )
            return [base]
        return sorted(base.rglob(self.manifest_filename), key=lambda path: path.as_posix())

    def load(
        self,
        root: str | Path,
        *,
        registry: ComponentRegistry | None = None,
        strict: bool = False,
    ) -> DomainPackLoaderSnapshot:
        target_registry = registry or self.component_registry
        if target_registry is None:
            raise ValueError("DomainPackLoader requires a ComponentRegistry to load Domain Packs.")
        self.component_registry = target_registry

        results: list[DomainPackLoadResult] = []
        for manifest_path in self.discover(root):
            result = self.load_manifest(manifest_path, registry=target_registry, strict=strict)
            results.append(result)
        self._results.extend(results)
        return self._build_snapshot(results)

    def load_manifest(
        self,
        path: str | Path,
        *,
        registry: ComponentRegistry | None = None,
        strict: bool = False,
    ) -> DomainPackLoadResult:
        manifest_path = Path(path)
        target_registry = registry or self.component_registry
        if target_registry is None:
            raise ValueError("DomainPackLoader requires a ComponentRegistry to load Domain Packs.")

        try:
            manifest = DomainPackManifest.from_file(manifest_path)
            contract = build_domain_pack_contract(manifest)

            if target_registry.get(contract.component.name) is not None:
                result = DomainPackLoadResult(
                    status=DomainPackLoadStatus.SKIPPED,
                    manifest_path=manifest_path.as_posix(),
                    pack_root=manifest_path.parent.as_posix(),
                    manifest=manifest,
                    contract=contract,
                    component=target_registry.require(contract.component.name),
                    errors=(f"Domain Pack already loaded: {contract.component.name}",),
                    metadata={"loader_contract": DOMAIN_PACK_LOADER_CONTRACT},
                )
                if strict:
                    raise ValueError(result.errors[0])
                return result

            missing_assets = self._missing_required_assets(manifest, manifest_path.parent)
            if missing_assets:
                message = "Missing required Domain Pack assets: " + ", ".join(missing_assets)
                if strict:
                    raise ValueError(message)
                return DomainPackLoadResult(
                    status=DomainPackLoadStatus.FAILED,
                    manifest_path=manifest_path.as_posix(),
                    pack_root=manifest_path.parent.as_posix(),
                    manifest=manifest,
                    contract=contract,
                    errors=(message,),
                    metadata={"loader_contract": DOMAIN_PACK_LOADER_CONTRACT},
                )

            descriptor = self._descriptor_for_load(contract, manifest_path)
            registered = target_registry.register(descriptor)
            return DomainPackLoadResult(
                status=DomainPackLoadStatus.LOADED,
                manifest_path=manifest_path.as_posix(),
                pack_root=manifest_path.parent.as_posix(),
                manifest=manifest,
                contract=DomainPackContract(manifest=manifest, component=registered),
                component=registered,
                metadata={"loader_contract": DOMAIN_PACK_LOADER_CONTRACT},
            )
        except Exception as exc:
            if strict:
                raise
            return DomainPackLoadResult(
                status=DomainPackLoadStatus.FAILED,
                manifest_path=manifest_path.as_posix(),
                pack_root=manifest_path.parent.as_posix(),
                errors=(str(exc),),
                metadata={"loader_contract": DOMAIN_PACK_LOADER_CONTRACT},
            )

    def results(self) -> tuple[DomainPackLoadResult, ...]:
        return tuple(self._results)

    def snapshot(self) -> DomainPackLoaderSnapshot:
        return self._build_snapshot(self._results)

    def export(self, *, format: str = "dict") -> Dict[str, Any] | str:
        snapshot = self.snapshot()
        if format == "dict":
            return snapshot.to_dict()
        if format == "json":
            return snapshot.to_json()
        raise ValueError(f"Unsupported Domain Pack loader export format: {format}")

    def _descriptor_for_load(
        self,
        contract: DomainPackContract,
        manifest_path: Path,
    ) -> ComponentDescriptor:
        component = contract.component
        metadata = dict(component.metadata)
        metadata.update(
            {
                "pack_root": manifest_path.parent.as_posix(),
                "manifest_path": manifest_path.as_posix(),
                "loader_contract": DOMAIN_PACK_LOADER_CONTRACT,
                "domain_code_imported": False,
            }
        )
        return ComponentDescriptor(
            name=component.name,
            class_name=component.class_name,
            role=component.role,
            version=component.version,
            provider=component.provider,
            capabilities=component.capabilities,
            dependencies=component.dependencies,
            tags=component.tags,
            state=ComponentState.REGISTERED,
            metadata=metadata,
        )

    def _missing_required_assets(self, manifest: DomainPackManifest, pack_root: Path) -> tuple[str, ...]:
        missing: list[str] = []
        for asset in manifest.assets:
            if asset.required and not (pack_root / asset.path).exists():
                missing.append(asset.path)
        return tuple(missing)

    def _build_snapshot(self, results: Iterable[DomainPackLoadResult]) -> DomainPackLoaderSnapshot:
        values = tuple(results)
        return DomainPackLoaderSnapshot(
            contract=DOMAIN_PACK_LOADER_CONTRACT,
            pack_count=len(values),
            loaded_count=sum(1 for item in values if item.status == DomainPackLoadStatus.LOADED),
            failed_count=sum(1 for item in values if item.status == DomainPackLoadStatus.FAILED),
            skipped_count=sum(1 for item in values if item.status == DomainPackLoadStatus.SKIPPED),
            results=values,
        )
