from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Iterable, Mapping


class ComponentState(str, Enum):
    REGISTERED = "registered"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


_ALLOWED_TRANSITIONS = {
    ComponentState.REGISTERED: {ComponentState.INITIALIZED, ComponentState.STOPPED},
    ComponentState.INITIALIZED: {ComponentState.ACTIVE, ComponentState.STOPPED},
    ComponentState.ACTIVE: {ComponentState.PAUSED, ComponentState.STOPPED},
    ComponentState.PAUSED: {ComponentState.ACTIVE, ComponentState.STOPPED},
    ComponentState.STOPPED: {ComponentState.REGISTERED},
}


@dataclass(frozen=True)
class ComponentDescriptor:
    """Stable registry contract for runtime-visible capabilities.

    A descriptor describes a component without exposing its implementation.
    Future Plugin SDK, REST and MCP layers should consume this contract instead
    of reaching into runtime internals.
    """

    name: str
    class_name: str
    role: str
    version: str = "0.1.0"
    provider: str = "aca"
    capabilities: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    state: ComponentState = ComponentState.REGISTERED
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Component name is required.")
        if not self.class_name or not self.class_name.strip():
            raise ValueError("Component class_name is required.")
        if not self.role or not self.role.strip():
            raise ValueError("Component role is required.")
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "tags", tuple(self.tags))
        if not isinstance(self.state, ComponentState):
            object.__setattr__(self, "state", ComponentState(self.state))

    def with_state(self, state: ComponentState | str) -> "ComponentDescriptor":
        return replace(self, state=ComponentState(state))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "class_name": self.class_name,
            "role": self.role,
            "version": self.version,
            "provider": self.provider,
            "capabilities": list(self.capabilities),
            "dependencies": list(self.dependencies),
            "tags": list(self.tags),
            "state": self.state.value,
            "metadata": dict(self.metadata),
        }


class ComponentRegistry:
    """Runtime service for deterministic component discovery.

    Components are registered through descriptors and never depend on one
    another. The registry owns metadata, lifecycle state and contract validation.
    """

    def __init__(self) -> None:
        self._components: Dict[str, ComponentDescriptor] = {}

    def register(self, descriptor: ComponentDescriptor) -> ComponentDescriptor:
        if descriptor.name in self._components:
            raise ValueError(f"Component already registered: {descriptor.name}")
        self._validate_dependencies(descriptor)
        self._components[descriptor.name] = descriptor
        return descriptor

    def register_instance(
        self,
        *,
        name: str,
        instance: Any,
        role: str,
        version: str = "0.1.0",
        provider: str = "aca",
        capabilities: Iterable[str] = (),
        dependencies: Iterable[str] = (),
        tags: Iterable[str] = (),
        metadata: Mapping[str, Any] | None = None,
        state: ComponentState | str = ComponentState.REGISTERED,
    ) -> ComponentDescriptor:
        descriptor = ComponentDescriptor(
            name=name,
            class_name=instance.__class__.__name__,
            role=role,
            version=version,
            provider=provider,
            capabilities=tuple(capabilities),
            dependencies=tuple(dependencies),
            tags=tuple(tags),
            state=ComponentState(state),
            metadata=metadata or {},
        )
        return self.register(descriptor)

    def get(self, name: str) -> ComponentDescriptor | None:
        return self._components.get(name)

    def require(self, name: str) -> ComponentDescriptor:
        descriptor = self.get(name)
        if descriptor is None:
            raise KeyError(f"Component is not registered: {name}")
        return descriptor

    def set_state(self, name: str, state: ComponentState | str) -> ComponentDescriptor:
        descriptor = self.require(name)
        next_state = ComponentState(state)
        allowed = _ALLOWED_TRANSITIONS.get(descriptor.state, set())
        if next_state != descriptor.state and next_state not in allowed:
            raise ValueError(
                f"Invalid component state transition for {name}: "
                f"{descriptor.state.value} -> {next_state.value}"
            )
        updated = descriptor.with_state(next_state)
        self._components[name] = updated
        return updated

    def initialize(self, name: str) -> ComponentDescriptor:
        return self.set_state(name, ComponentState.INITIALIZED)

    def activate(self, name: str) -> ComponentDescriptor:
        return self.set_state(name, ComponentState.ACTIVE)

    def pause(self, name: str) -> ComponentDescriptor:
        return self.set_state(name, ComponentState.PAUSED)

    def stop(self, name: str) -> ComponentDescriptor:
        return self.set_state(name, ComponentState.STOPPED)

    def unregister(self, name: str) -> ComponentDescriptor:
        descriptor = self.require(name)
        if descriptor.state == ComponentState.ACTIVE:
            raise ValueError(f"Active component must be stopped before unregistering: {name}")
        return self._components.pop(name)

    def list(self) -> list[ComponentDescriptor]:
        return [self._components[name] for name in sorted(self._components)]

    def find_by_capability(self, capability: str) -> list[ComponentDescriptor]:
        return [descriptor for descriptor in self.list() if capability in descriptor.capabilities]

    def snapshot(self) -> Dict[str, Any]:
        components = [descriptor.to_dict() for descriptor in self.list()]
        states: Dict[str, int] = {}
        for descriptor in components:
            states[descriptor["state"]] = states.get(descriptor["state"], 0) + 1
        return {
            "component_count": len(components),
            "states": states,
            "components": components,
        }

    def export(self, *, format: str = "dict") -> Dict[str, Any] | str:
        snapshot = self.snapshot()
        if format == "dict":
            return snapshot
        if format == "json":
            return json.dumps(snapshot, ensure_ascii=False, indent=2)
        raise ValueError(f"Unsupported component registry export format: {format}")

    def _validate_dependencies(self, descriptor: ComponentDescriptor) -> None:
        missing = [name for name in descriptor.dependencies if name not in self._components]
        if missing:
            raise ValueError(
                f"Component {descriptor.name} declares missing dependencies: {', '.join(missing)}"
            )


def build_registry_from_runtime(runtime: Any) -> ComponentRegistry:
    registry = ComponentRegistry()
    for name, spec in _runtime_component_specs().items():
        instance = getattr(runtime, name, None)
        if instance is None:
            continue
        registry.register_instance(
            name=name,
            instance=instance,
            role=spec["role"],
            capabilities=spec.get("capabilities", ()),
            tags=spec.get("tags", ()),
            metadata={"runtime_owned": True},
        )
        registry.initialize(name)
        registry.activate(name)
    return registry


def _runtime_component_specs() -> Dict[str, Dict[str, Any]]:
    return {
        "conversation_manager": {
            "role": "conversation lifecycle",
            "capabilities": ("conversation.state", "conversation.history"),
            "tags": ("runtime", "state"),
        },
        "intent_matcher": {
            "role": "zero-cost intent detection",
            "capabilities": ("intent.match",),
            "tags": ("zero-cost", "runtime-intelligence"),
        },
        "action_planner": {
            "role": "zero-cost action selection",
            "capabilities": ("action.plan",),
            "tags": ("zero-cost", "runtime-intelligence"),
        },
        "flow_router": {
            "role": "zero-cost flow routing",
            "capabilities": ("flow.route",),
            "tags": ("zero-cost", "runtime-intelligence"),
        },
        "decision_graph_engine": {
            "role": "zero-cost decision graph construction",
            "capabilities": ("decision_graph.build", "decision_graph.explain"),
            "tags": ("zero-cost", "runtime-intelligence"),
        },
        "policy_manager": {
            "role": "policy decisioning",
            "capabilities": ("policy.evaluate",),
            "tags": ("runtime", "governance"),
        },
        "tool_engine": {
            "role": "tool execution",
            "capabilities": ("tool.execute",),
            "tags": ("runtime", "tools"),
        },
        "memory_engine": {
            "role": "memory consolidation",
            "capabilities": ("memory.consolidate", "memory.retrieve"),
            "tags": ("runtime", "memory"),
        },
        "context_manager": {
            "role": "context assembly",
            "capabilities": ("context.build",),
            "tags": ("runtime", "context"),
        },
        "metrics_engine": {
            "role": "runtime metrics aggregation",
            "capabilities": ("metrics.snapshot", "metrics.export"),
            "tags": ("observability", "runtime"),
        },
        "event_bus": {
            "role": "internal event publication",
            "capabilities": ("event.publish", "event.read"),
            "tags": ("observability", "runtime"),
        },
        "plugin_validator": {
            "role": "plugin contract validator",
            "capabilities": ("plugin.validate", "plugin.contract.check"),
            "tags": ("plugin-sdk", "runtime", "governance"),
        },
        "plugin_loader": {
            "role": "plugin manifest loader",
            "capabilities": ("plugin.discover", "plugin.load", "plugin.export"),
            "tags": ("plugin-sdk", "runtime"),
        },
        "plugin_lifecycle": {
            "role": "plugin lifecycle manager",
            "capabilities": (
                "plugin.initialize",
                "plugin.activate",
                "plugin.pause",
                "plugin.stop",
                "plugin.unload",
                "plugin.lifecycle.export",
            ),
            "tags": ("plugin-sdk", "runtime", "governance"),
        },
    }
