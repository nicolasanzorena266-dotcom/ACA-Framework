from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from aca_os.domain_pack_loader import (
    DomainPackLoader,
    DomainPackLoaderSnapshot,
    DomainPackLoadStatus,
)
from aca_os.domain_pack_manifest import DomainPackAsset, DomainPackManifest


DOMAIN_PACK_RUNTIME_CONTRACT = "domain_pack_runtime.v1"


@dataclass(frozen=True)
class RuntimeDomainPackAsset:
    """Runtime-visible asset payload loaded from a Domain Pack.

    Assets stay data-only. The runtime reads JSON/text/markdown/csv content,
    never imports Python code from a pack and never gives packs internal object
    references.
    """

    name: str
    kind: str
    path: str
    format: str
    description: str = ""
    content: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "path": self.path,
            "format": self.format,
            "description": self.description,
            "content": self.content,
        }


@dataclass(frozen=True)
class RuntimeDomainPack:
    """A loaded Domain Pack as exposed to Runtime consumers."""

    name: str
    version: str
    domain: str
    provider: str
    description: str
    manifest_path: str
    pack_root: str
    capabilities: tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    assets: tuple[RuntimeDomainPackAsset, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_manifest(cls, manifest: DomainPackManifest, *, manifest_path: str, pack_root: str) -> "RuntimeDomainPack":
        root = Path(pack_root)
        assets = tuple(_load_asset(asset, root) for asset in manifest.assets)
        return cls(
            name=manifest.name,
            version=manifest.version,
            domain=manifest.domain,
            provider=manifest.provider,
            description=manifest.description,
            manifest_path=manifest_path,
            pack_root=pack_root,
            capabilities=tuple(item.to_dict() for item in manifest.capabilities),
            assets=assets,
            tags=manifest.tags,
            metadata={
                **dict(manifest.metadata),
                "domain_code_imported": False,
                "runtime_contract": DOMAIN_PACK_RUNTIME_CONTRACT,
            },
        )

    def asset(self, name: str) -> RuntimeDomainPackAsset:
        for asset in self.assets:
            if asset.name == name:
                return asset
        raise KeyError(f"Domain Pack asset not found: {name}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "domain": self.domain,
            "provider": self.provider,
            "description": self.description,
            "manifest_path": self.manifest_path,
            "pack_root": self.pack_root,
            "capabilities": list(self.capabilities),
            "assets": [asset.to_dict() for asset in self.assets],
            "asset_count": len(self.assets),
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    def to_context(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "domain": self.domain,
            "capabilities": [item["name"] for item in self.capabilities],
            "assets": {asset.name: asset.content for asset in self.assets},
            "asset_index": {
                asset.name: {
                    "kind": asset.kind,
                    "format": asset.format,
                    "path": asset.path,
                }
                for asset in self.assets
            },
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DomainPackRuntimeSnapshot:
    contract: str
    pack_count: int
    loaded_count: int
    failed_count: int
    skipped_count: int
    packs: tuple[RuntimeDomainPack, ...] = field(default_factory=tuple)
    loader: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "pack_count": self.pack_count,
            "loaded_count": self.loaded_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "packs": [pack.to_dict() for pack in self.packs],
            "loader": dict(self.loader),
            "metadata": dict(self.metadata),
        }

    def to_context(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "pack_count": self.pack_count,
            "domains": {pack.domain: pack.to_context() for pack in self.packs},
            "packs": {pack.name: pack.to_context() for pack in self.packs},
            "capabilities": sorted(
                {capability["name"] for pack in self.packs for capability in pack.capabilities}
            ),
            "domain_code_imported": False,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class DomainPackRuntime:
    """Runtime integration boundary for loaded Domain Packs.

    This class turns validated, loader-registered Domain Packs into observable
    runtime context. It does not route flows, import domain code or mutate core
    components. ACAOSRuntime owns when this context is attached to execution.
    """

    def __init__(self, loader: DomainPackLoader) -> None:
        self.loader = loader
        self._packs: Dict[str, RuntimeDomainPack] = {}
        self._last_loader_snapshot: Dict[str, Any] = {}

    def load(self, root: str | Path, *, strict: bool = False) -> DomainPackRuntimeSnapshot:
        loader_snapshot = self.loader.load(root, strict=strict)
        self._last_loader_snapshot = loader_snapshot.to_dict()
        self._sync_from_loader_snapshot(loader_snapshot)
        return self.snapshot(loader=loader_snapshot.to_dict())

    def snapshot(self, *, loader: Mapping[str, Any] | None = None) -> DomainPackRuntimeSnapshot:
        loader_data = dict(loader or self._last_loader_snapshot)
        loaded_count = int(loader_data.get("loaded_count", len(self._packs))) if loader_data else len(self._packs)
        failed_count = int(loader_data.get("failed_count", 0)) if loader_data else 0
        skipped_count = int(loader_data.get("skipped_count", 0)) if loader_data else 0
        packs = tuple(self._packs[name] for name in sorted(self._packs))
        return DomainPackRuntimeSnapshot(
            contract=DOMAIN_PACK_RUNTIME_CONTRACT,
            pack_count=len(packs),
            loaded_count=loaded_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            packs=packs,
            loader=loader_data,
            metadata={
                "domain_code_imported": False,
                "source_of_truth": "execution_trace_and_runtime_context",
            },
        )

    def export(self, *, format: str = "dict") -> Dict[str, Any] | str:
        snapshot = self.snapshot()
        if format == "dict":
            return snapshot.to_dict()
        if format == "json":
            return snapshot.to_json()
        raise ValueError(f"Unsupported Domain Pack runtime export format: {format}")

    def context(self) -> Dict[str, Any]:
        return self.snapshot().to_context()

    def get(self, name: str) -> RuntimeDomainPack:
        try:
            return self._packs[name]
        except KeyError as exc:
            raise KeyError(f"Domain Pack not loaded: {name}") from exc

    def list(self) -> tuple[RuntimeDomainPack, ...]:
        return tuple(self._packs[name] for name in sorted(self._packs))

    def _sync_from_loader_snapshot(self, snapshot: DomainPackLoaderSnapshot) -> None:
        for result in snapshot.results:
            if result.status not in {DomainPackLoadStatus.LOADED, DomainPackLoadStatus.SKIPPED}:
                continue
            if result.manifest is None:
                continue
            if result.manifest.name in self._packs:
                continue
            self._packs[result.manifest.name] = RuntimeDomainPack.from_manifest(
                result.manifest,
                manifest_path=result.manifest_path,
                pack_root=result.pack_root,
            )


def _load_asset(asset: DomainPackAsset, root: Path) -> RuntimeDomainPackAsset:
    path = root / asset.path
    content = _read_asset_content(path, asset.format)
    return RuntimeDomainPackAsset(
        name=asset.name,
        kind=asset.kind,
        path=asset.path,
        format=asset.format,
        description=asset.description,
        content=content,
    )


def _read_asset_content(path: Path, format: str) -> Any:
    normalized = format.lower().strip()
    if normalized == "json":
        return json.loads(path.read_text(encoding="utf-8"))
    if normalized == "json-dir":
        return {
            item.stem: json.loads(item.read_text(encoding="utf-8"))
            for item in sorted(path.glob("*.json"), key=lambda item: item.name)
        }
    if normalized in {"markdown", "md", "text", "txt", "csv", "yaml", "yml"}:
        return path.read_text(encoding="utf-8")
    raise ValueError(f"Unsupported runtime Domain Pack asset format: {format}")
