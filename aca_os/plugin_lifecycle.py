from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Iterable, Mapping

from aca_os.component_registry import ComponentRegistry, ComponentState
from aca_os.plugin_loader import PluginLoadResult, PluginLoader, PluginLoadStatus
from aca_os.plugin_manifest import PluginManifest


PLUGIN_LIFECYCLE_CONTRACT = "plugin_lifecycle.v1"


class PluginLifecycleState(str, Enum):
    REGISTERED = "registered"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    UNLOADED = "unloaded"
    FAILED = "failed"


_ALLOWED_TRANSITIONS = {
    PluginLifecycleState.REGISTERED: {
        PluginLifecycleState.INITIALIZED,
        PluginLifecycleState.STOPPED,
        PluginLifecycleState.UNLOADED,
        PluginLifecycleState.FAILED,
    },
    PluginLifecycleState.INITIALIZED: {
        PluginLifecycleState.ACTIVE,
        PluginLifecycleState.STOPPED,
        PluginLifecycleState.UNLOADED,
        PluginLifecycleState.FAILED,
    },
    PluginLifecycleState.ACTIVE: {
        PluginLifecycleState.PAUSED,
        PluginLifecycleState.STOPPED,
        PluginLifecycleState.FAILED,
    },
    PluginLifecycleState.PAUSED: {
        PluginLifecycleState.ACTIVE,
        PluginLifecycleState.STOPPED,
        PluginLifecycleState.UNLOADED,
        PluginLifecycleState.FAILED,
    },
    PluginLifecycleState.STOPPED: {
        PluginLifecycleState.REGISTERED,
        PluginLifecycleState.UNLOADED,
        PluginLifecycleState.FAILED,
    },
    PluginLifecycleState.FAILED: {PluginLifecycleState.STOPPED, PluginLifecycleState.UNLOADED},
    PluginLifecycleState.UNLOADED: set(),
}

_COMPONENT_STATE_MAP = {
    PluginLifecycleState.REGISTERED: ComponentState.REGISTERED,
    PluginLifecycleState.INITIALIZED: ComponentState.INITIALIZED,
    PluginLifecycleState.ACTIVE: ComponentState.ACTIVE,
    PluginLifecycleState.PAUSED: ComponentState.PAUSED,
    PluginLifecycleState.STOPPED: ComponentState.STOPPED,
}


@dataclass(frozen=True)
class PluginLifecycleEvent:
    sequence: int
    plugin_name: str
    action: str
    from_state: str | None
    to_state: str | None
    success: bool
    message: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence": self.sequence,
            "plugin_name": self.plugin_name,
            "action": self.action,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "success": self.success,
            "message": self.message,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PluginLifecycleRecord:
    plugin_name: str
    state: PluginLifecycleState
    manifest: PluginManifest | None = None
    manifest_path: str | None = None
    plugin_root: str | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def with_state(
        self,
        state: PluginLifecycleState | str,
        *,
        errors: Iterable[str] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "PluginLifecycleRecord":
        merged_metadata = dict(self.metadata)
        if metadata:
            merged_metadata.update(metadata)
        return replace(
            self,
            state=PluginLifecycleState(state),
            errors=tuple(errors) if errors is not None else self.errors,
            metadata=merged_metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plugin_name": self.plugin_name,
            "state": self.state.value,
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "manifest_path": self.manifest_path,
            "plugin_root": self.plugin_root,
            "errors": list(self.errors),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PluginLifecycleSnapshot:
    contract: str
    plugin_count: int
    states: Mapping[str, int]
    records: tuple[PluginLifecycleRecord, ...] = field(default_factory=tuple)
    events: tuple[PluginLifecycleEvent, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "plugin_count": self.plugin_count,
            "states": dict(self.states),
            "records": [record.to_dict() for record in self.records],
            "events": [event.to_dict() for event in self.events],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class PluginLifecycleManager:
    """Deterministic lifecycle boundary for Plugin SDK plugins.

    Sprint 38 still does not import or execute plugin entrypoints. Lifecycle is
    owned as Runtime metadata plus Component Registry state, making every plugin
    transition observable, reproducible and reversible where safe.
    """

    def __init__(
        self,
        *,
        component_registry: ComponentRegistry,
        plugin_loader: PluginLoader | None = None,
    ) -> None:
        self.component_registry = component_registry
        self.plugin_loader = plugin_loader
        self._records: Dict[str, PluginLifecycleRecord] = {}
        self._events: list[PluginLifecycleEvent] = []
        self._sequence = 0

    def bind_registry(self, registry: ComponentRegistry) -> None:
        self.component_registry = registry

    def bind_loader(self, loader: PluginLoader) -> None:
        self.plugin_loader = loader

    def attach_load_result(self, result: PluginLoadResult) -> PluginLifecycleRecord | None:
        if result.status != PluginLoadStatus.LOADED or result.manifest is None:
            return None
        name = result.manifest.name
        record = PluginLifecycleRecord(
            plugin_name=name,
            state=PluginLifecycleState.REGISTERED,
            manifest=result.manifest,
            manifest_path=result.manifest_path,
            plugin_root=result.plugin_root,
            metadata={
                "lifecycle_contract": PLUGIN_LIFECYCLE_CONTRACT,
                "loaded": True,
                **dict(result.metadata),
            },
        )
        self._records[name] = record
        self._record_event(name, "register", None, record.state, True)
        return record

    def attach_many(self, results: Iterable[PluginLoadResult]) -> tuple[PluginLifecycleRecord, ...]:
        attached: list[PluginLifecycleRecord] = []
        for result in results:
            record = self.attach_load_result(result)
            if record is not None:
                attached.append(record)
        return tuple(attached)

    def load_plugins(self, root: str, *, strict: bool = False) -> Dict[str, Any]:
        if self.plugin_loader is None:
            raise ValueError("PluginLifecycleManager requires a PluginLoader to load plugins.")
        loader_snapshot = self.plugin_loader.load(root, registry=self.component_registry, strict=strict)
        self.attach_many(loader_snapshot.results)
        lifecycle_snapshot = self.snapshot().to_dict()
        output = loader_snapshot.to_dict()
        output["lifecycle"] = lifecycle_snapshot
        return output

    def initialize(self, plugin_name: str) -> PluginLifecycleRecord:
        return self.transition(plugin_name, PluginLifecycleState.INITIALIZED)

    def activate(self, plugin_name: str) -> PluginLifecycleRecord:
        return self.transition(plugin_name, PluginLifecycleState.ACTIVE)

    def pause(self, plugin_name: str) -> PluginLifecycleRecord:
        return self.transition(plugin_name, PluginLifecycleState.PAUSED)

    def stop(self, plugin_name: str) -> PluginLifecycleRecord:
        return self.transition(plugin_name, PluginLifecycleState.STOPPED)

    def reset(self, plugin_name: str) -> PluginLifecycleRecord:
        return self.transition(plugin_name, PluginLifecycleState.REGISTERED)

    def unload(self, plugin_name: str) -> PluginLifecycleRecord:
        record = self.require(plugin_name)
        if record.state == PluginLifecycleState.ACTIVE:
            raise ValueError(f"Active plugin must be stopped before unload: {plugin_name}")
        previous = record.state
        self._ensure_transition(record.state, PluginLifecycleState.UNLOADED, plugin_name)
        if self.component_registry.get(plugin_name) is not None:
            self.component_registry.unregister(plugin_name)
        updated = record.with_state(PluginLifecycleState.UNLOADED)
        self._records[plugin_name] = updated
        self._record_event(plugin_name, "unload", previous, PluginLifecycleState.UNLOADED, True)
        return updated

    def transition(
        self,
        plugin_name: str,
        state: PluginLifecycleState | str,
    ) -> PluginLifecycleRecord:
        record = self.require(plugin_name)
        next_state = PluginLifecycleState(state)
        previous = record.state
        self._ensure_transition(previous, next_state, plugin_name)
        component_state = _COMPONENT_STATE_MAP.get(next_state)
        if component_state is not None:
            self.component_registry.set_state(plugin_name, component_state)
        updated = record.with_state(next_state)
        self._records[plugin_name] = updated
        self._record_event(plugin_name, f"transition:{next_state.value}", previous, next_state, True)
        return updated

    def mark_failed(self, plugin_name: str, message: str) -> PluginLifecycleRecord:
        record = self.require(plugin_name)
        previous = record.state
        self._ensure_transition(previous, PluginLifecycleState.FAILED, plugin_name)
        updated = record.with_state(PluginLifecycleState.FAILED, errors=(*record.errors, message))
        self._records[plugin_name] = updated
        self._record_event(plugin_name, "fail", previous, PluginLifecycleState.FAILED, False, message)
        return updated

    def get(self, plugin_name: str) -> PluginLifecycleRecord | None:
        return self._records.get(plugin_name)

    def require(self, plugin_name: str) -> PluginLifecycleRecord:
        record = self.get(plugin_name)
        if record is None:
            raise KeyError(f"Plugin lifecycle record does not exist: {plugin_name}")
        return record

    def list(self) -> list[PluginLifecycleRecord]:
        return [self._records[name] for name in sorted(self._records)]

    def events(self) -> tuple[PluginLifecycleEvent, ...]:
        return tuple(self._events)

    def snapshot(self) -> PluginLifecycleSnapshot:
        records = tuple(self.list())
        states: Dict[str, int] = {}
        for record in records:
            states[record.state.value] = states.get(record.state.value, 0) + 1
        return PluginLifecycleSnapshot(
            contract=PLUGIN_LIFECYCLE_CONTRACT,
            plugin_count=len(records),
            states=states,
            records=records,
            events=tuple(self._events),
        )

    def export(self, *, format: str = "dict") -> Dict[str, Any] | str:
        snapshot = self.snapshot()
        if format == "dict":
            return snapshot.to_dict()
        if format == "json":
            return snapshot.to_json()
        raise ValueError(f"Unsupported plugin lifecycle export format: {format}")

    def _ensure_transition(
        self,
        previous: PluginLifecycleState,
        next_state: PluginLifecycleState,
        plugin_name: str,
    ) -> None:
        allowed = _ALLOWED_TRANSITIONS.get(previous, set())
        if next_state != previous and next_state not in allowed:
            self._record_event(plugin_name, f"transition:{next_state.value}", previous, next_state, False)
            raise ValueError(
                f"Invalid plugin lifecycle transition for {plugin_name}: "
                f"{previous.value} -> {next_state.value}"
            )

    def _record_event(
        self,
        plugin_name: str,
        action: str,
        from_state: PluginLifecycleState | None,
        to_state: PluginLifecycleState | None,
        success: bool,
        message: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> PluginLifecycleEvent:
        self._sequence += 1
        event = PluginLifecycleEvent(
            sequence=self._sequence,
            plugin_name=plugin_name,
            action=action,
            from_state=from_state.value if from_state else None,
            to_state=to_state.value if to_state else None,
            success=success,
            message=message,
            metadata=metadata or {},
        )
        self._events.append(event)
        return event
