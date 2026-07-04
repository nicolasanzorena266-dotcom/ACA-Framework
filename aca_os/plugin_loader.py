from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from aca_os.component_registry import ComponentDescriptor, ComponentRegistry, ComponentState
from aca_os.plugin_manifest import PluginContract, PluginManifest, build_plugin_contract


DEFAULT_PLUGIN_MANIFEST = "plugin.json"
PLUGIN_LOADER_CONTRACT = "plugin_loader.v1"


class PluginLoadStatus(str, Enum):
    DISCOVERED = "discovered"
    LOADED = "loaded"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class PluginLoadResult:
    """Deterministic result of one plugin load attempt.

    Sprint 36 loads plugin metadata only. It never imports the declared
    entrypoint and never executes plugin code. Runtime visibility is achieved by
    projecting the manifest contract into the Component Registry.
    """

    status: PluginLoadStatus
    manifest_path: str
    plugin_root: str
    manifest: PluginManifest | None = None
    contract: PluginContract | None = None
    component: ComponentDescriptor | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def loaded(self) -> bool:
        return self.status == PluginLoadStatus.LOADED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "manifest_path": self.manifest_path,
            "plugin_root": self.plugin_root,
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "contract": self.contract.to_dict() if self.contract else None,
            "component": self.component.to_dict() if self.component else None,
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PluginLoaderSnapshot:
    contract: str
    plugin_count: int
    loaded_count: int
    failed_count: int
    skipped_count: int
    results: tuple[PluginLoadResult, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "plugin_count": self.plugin_count,
            "loaded_count": self.loaded_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "results": [result.to_dict() for result in self.results],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class PluginLoader:
    """Manifest-first plugin loader.

    The loader discovers plugin manifests, validates them through the Sprint 35
    contract and registers the resulting component descriptors. It deliberately
    avoids importing entrypoint modules; executable lifecycle is owned by later
    Plugin SDK stages.
    """

    def __init__(
        self,
        *,
        manifest_filename: str = DEFAULT_PLUGIN_MANIFEST,
        component_registry: ComponentRegistry | None = None,
    ) -> None:
        if not manifest_filename or not manifest_filename.strip():
            raise ValueError("Plugin manifest filename is required.")
        self.manifest_filename = manifest_filename
        self.component_registry = component_registry
        self._results: List[PluginLoadResult] = []

    def bind_registry(self, registry: ComponentRegistry) -> None:
        self.component_registry = registry

    def discover(self, root: str | Path) -> list[Path]:
        base = Path(root)
        if not base.exists():
            raise FileNotFoundError(f"Plugin path does not exist: {base}")
        if base.is_file():
            if base.name != self.manifest_filename:
                raise ValueError(
                    f"Expected plugin manifest file named {self.manifest_filename}: {base}"
                )
            return [base]
        return sorted(base.rglob(self.manifest_filename), key=lambda path: path.as_posix())

    def load(
        self,
        root: str | Path,
        *,
        registry: ComponentRegistry | None = None,
        strict: bool = False,
    ) -> PluginLoaderSnapshot:
        target_registry = registry or self.component_registry
        if target_registry is None:
            raise ValueError("PluginLoader requires a ComponentRegistry to load plugins.")
        self.component_registry = target_registry

        results: list[PluginLoadResult] = []
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
    ) -> PluginLoadResult:
        manifest_path = Path(path)
        target_registry = registry or self.component_registry
        if target_registry is None:
            raise ValueError("PluginLoader requires a ComponentRegistry to load plugins.")

        try:
            manifest = PluginManifest.from_file(manifest_path)
            contract = build_plugin_contract(manifest)
            if target_registry.get(contract.component.name) is not None:
                result = PluginLoadResult(
                    status=PluginLoadStatus.SKIPPED,
                    manifest_path=manifest_path.as_posix(),
                    plugin_root=manifest_path.parent.as_posix(),
                    manifest=manifest,
                    contract=contract,
                    component=target_registry.require(contract.component.name),
                    errors=(f"Plugin already loaded: {contract.component.name}",),
                    metadata={"loader_contract": PLUGIN_LOADER_CONTRACT},
                )
                if strict:
                    raise ValueError(result.errors[0])
                return result

            descriptor = self._descriptor_for_load(contract, manifest_path)
            registered = target_registry.register(descriptor)
            return PluginLoadResult(
                status=PluginLoadStatus.LOADED,
                manifest_path=manifest_path.as_posix(),
                plugin_root=manifest_path.parent.as_posix(),
                manifest=manifest,
                contract=PluginContract(manifest=manifest, component=registered),
                component=registered,
                metadata={"loader_contract": PLUGIN_LOADER_CONTRACT},
            )
        except Exception as exc:  # keep loader observable instead of partially silent
            if strict:
                raise
            return PluginLoadResult(
                status=PluginLoadStatus.FAILED,
                manifest_path=manifest_path.as_posix(),
                plugin_root=manifest_path.parent.as_posix(),
                errors=(str(exc),),
                metadata={"loader_contract": PLUGIN_LOADER_CONTRACT},
            )

    def results(self) -> tuple[PluginLoadResult, ...]:
        return tuple(self._results)

    def snapshot(self) -> PluginLoaderSnapshot:
        return self._build_snapshot(self._results)

    def export(self, *, format: str = "dict") -> Dict[str, Any] | str:
        snapshot = self.snapshot()
        if format == "dict":
            return snapshot.to_dict()
        if format == "json":
            return snapshot.to_json()
        raise ValueError(f"Unsupported plugin loader export format: {format}")

    def _descriptor_for_load(
        self,
        contract: PluginContract,
        manifest_path: Path,
    ) -> ComponentDescriptor:
        component = contract.component
        metadata = dict(component.metadata)
        metadata.update(
            {
                "plugin_root": manifest_path.parent.as_posix(),
                "manifest_path": manifest_path.as_posix(),
                "loader_contract": PLUGIN_LOADER_CONTRACT,
                "entrypoint_imported": False,
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

    def _build_snapshot(self, results: Iterable[PluginLoadResult]) -> PluginLoaderSnapshot:
        values = tuple(results)
        return PluginLoaderSnapshot(
            contract=PLUGIN_LOADER_CONTRACT,
            plugin_count=len(values),
            loaded_count=sum(1 for item in values if item.status == PluginLoadStatus.LOADED),
            failed_count=sum(1 for item in values if item.status == PluginLoadStatus.FAILED),
            skipped_count=sum(1 for item in values if item.status == PluginLoadStatus.SKIPPED),
            results=values,
        )
