from __future__ import annotations

import importlib.util
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

_PLUGIN_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_CAPABILITY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:[._][a-z][a-z0-9_]*)*$")
_SUPPORTED_API_VERSIONS = {1}
_SUPPORTED_PLUGIN_TYPES = {"domain", "generic", "tool", "policy"}
_DEFAULT_FALLBACK_CAPABILITY = "generic.open_chat"


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.lower() == "null":
        return None
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    active_top_key: str | None = None
    active_list_item: Dict[str, Any] | None = None

    for raw_line in text.splitlines():
        without_comment = raw_line.split("#", 1)[0].rstrip()
        if not without_comment.strip():
            continue

        indent = len(without_comment) - len(without_comment.lstrip(" "))
        stripped = without_comment.strip()

        if indent == 0:
            if ":" not in stripped:
                raise ValueError(f"Invalid manifest line: {raw_line}")
            key, value = stripped.split(":", 1)
            key = key.strip()
            if value.strip() == "":
                result[key] = {}
                active_top_key = key
                active_list_item = None
            else:
                result[key] = _parse_scalar(value)
                active_top_key = None
                active_list_item = None
            continue

        if active_top_key is None:
            raise ValueError(f"Nested manifest line without parent: {raw_line}")

        parent = result.get(active_top_key)
        if stripped.startswith("- "):
            if not isinstance(parent, list):
                parent = []
                result[active_top_key] = parent
            item = stripped[2:].strip()
            if ":" in item:
                key, value = item.split(":", 1)
                active_list_item = {key.strip(): _parse_scalar(value)}
                parent.append(active_list_item)
            else:
                parent.append(_parse_scalar(item))
                active_list_item = None
            continue

        if ":" not in stripped:
            raise ValueError(f"Invalid nested manifest line: {raw_line}")
        if not isinstance(parent, dict):
            if isinstance(parent, list) and active_list_item is not None:
                key, value = stripped.split(":", 1)
                active_list_item[key.strip()] = _parse_scalar(value)
                continue
            raise ValueError(f"Cannot add mapping values under list key: {active_top_key}")
        key, value = stripped.split(":", 1)
        parent[key.strip()] = _parse_scalar(value)

    return result


def _load_mapping(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("Plugin manifest JSON must be an object.")
        return payload
    return _parse_simple_yaml(text)


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, Mapping) and not value:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(str(item) for item in value)
    raise ValueError("Expected a string or list of strings.")


@dataclass(frozen=True)
class PublicAction:
    id: str
    label: str
    capability: str
    mode: str = "interaction"
    requires_real_tool: bool = False
    enabled: bool = True
    disabled_reason: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PublicAction":
        action = cls(
            id=str(payload.get("id", "")).strip(),
            label=str(payload.get("label", "")).strip(),
            capability=str(payload.get("capability", "")).strip(),
            mode=str(payload.get("mode", "interaction")).strip() or "interaction",
            requires_real_tool=bool(payload.get("requires_real_tool", False)),
            enabled=bool(payload.get("enabled", True)),
            disabled_reason=(None if payload.get("disabled_reason") is None else str(payload.get("disabled_reason")).strip()),
        )
        if not action.id:
            raise ValueError("Public action id is required.")
        if not action.label:
            raise ValueError(f"Public action {action.id} must declare a label.")
        if not _CAPABILITY_PATTERN.match(action.capability) or "." not in action.capability:
            raise ValueError(f"Public action {action.id} must point to a namespaced capability.")
        if not action.enabled and not action.disabled_reason:
            raise ValueError(f"Disabled public action {action.id} must declare disabled_reason.")
        return action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "capability": self.capability,
            "mode": self.mode,
            "requires_real_tool": self.requires_real_tool,
            "enabled": self.enabled,
            "disabled_reason": self.disabled_reason,
        }


def _as_public_actions(value: Any) -> tuple[PublicAction, ...]:
    if value is None or (isinstance(value, Mapping) and not value):
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise ValueError("public_actions must be a list of action mappings.")
    actions: list[PublicAction] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("Each public action must be a mapping.")
        actions.append(PublicAction.from_mapping(item))
    return tuple(actions)


@dataclass(frozen=True)
class PluginIdentity:
    id: str
    type: str
    version: str
    display_name: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PluginIdentity":
        identity = cls(
            id=str(payload.get("id", "")).strip(),
            type=str(payload.get("type", "")).strip(),
            version=str(payload.get("version", "")).strip(),
            display_name=str(payload.get("display_name", "")).strip(),
        )
        if not _PLUGIN_ID_PATTERN.match(identity.id):
            raise ValueError(f"Invalid plugin id: {identity.id}")
        if identity.type not in _SUPPORTED_PLUGIN_TYPES:
            raise ValueError(f"Unsupported plugin type: {identity.type}")
        if not identity.version:
            raise ValueError("Plugin version is required.")
        if not identity.display_name:
            raise ValueError("Plugin display_name is required.")
        return identity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "version": self.version,
            "display_name": self.display_name,
        }


@dataclass(frozen=True)
class PluginRequires:
    aca_core: str = ">=0.4.0"
    aca_plugin_sdk: str = "^1.0.0"

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "PluginRequires":
        payload = payload or {}
        return cls(
            aca_core=str(payload.get("aca_core", ">=0.4.0")),
            aca_plugin_sdk=str(payload.get("aca_plugin_sdk", "^1.0.0")),
        )

    def to_dict(self) -> Dict[str, str]:
        return {"aca_core": self.aca_core, "aca_plugin_sdk": self.aca_plugin_sdk}


@dataclass(frozen=True)
class PluginExports:
    semantic: bool = False
    planner: bool = False
    policy: bool = False
    prompts: bool = False
    knowledge: bool = False
    tools: bool = False
    evals: bool = False
    traces: bool = False
    assets: bool = False

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any] | None) -> "PluginExports":
        payload = payload or {}
        names = cls.__dataclass_fields__.keys()
        return cls(**{name: bool(payload.get(name, False)) for name in names})

    def to_dict(self) -> Dict[str, bool]:
        return {name: bool(getattr(self, name)) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class PluginManifest:
    api_version: int
    plugin: PluginIdentity
    requires: PluginRequires
    exports: PluginExports
    handles: tuple[str, ...] = field(default_factory=tuple)
    blocked_capabilities: tuple[str, ...] = field(default_factory=tuple)
    public_actions: tuple[PublicAction, ...] = field(default_factory=tuple)
    path: str | None = None

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any], *, path: Path | None = None) -> "PluginManifest":
        api_version = int(payload.get("api_version", 0))
        if api_version not in _SUPPORTED_API_VERSIONS:
            raise ValueError(f"Unsupported manifest api_version: {api_version}")
        identity = PluginIdentity.from_mapping(payload.get("plugin") or {})
        manifest = cls(
            api_version=api_version,
            plugin=identity,
            requires=PluginRequires.from_mapping(payload.get("requires") or {}),
            exports=PluginExports.from_mapping(payload.get("exports") or {}),
            handles=_as_tuple(payload.get("handles")),
            blocked_capabilities=_as_tuple(payload.get("blocked_capabilities")),
            public_actions=_as_public_actions(payload.get("public_actions")),
            path=str(path.parent) if path else None,
        )
        manifest.validate()
        return manifest

    @classmethod
    def from_file(cls, path: str | Path) -> "PluginManifest":
        manifest_path = Path(path)
        return cls.from_mapping(_load_mapping(manifest_path), path=manifest_path)

    @property
    def id(self) -> str:
        return self.plugin.id

    @property
    def capabilities(self) -> tuple[str, ...]:
        return self.handles

    def validate(self) -> None:
        if not self.handles:
            raise ValueError(f"Plugin {self.id} must declare at least one handled capability.")
        invalid = [cap for cap in self.handles + self.blocked_capabilities if not _CAPABILITY_PATTERN.match(cap)]
        if invalid:
            raise ValueError(f"Invalid capability names for plugin {self.id}: {invalid}")
        declared = set(self.handles) | set(self.blocked_capabilities)
        unbound_actions = [action.id for action in self.public_actions if action.capability not in declared]
        if unbound_actions:
            raise ValueError(f"Public actions must point to handled or blocked capabilities for plugin {self.id}: {unbound_actions}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "api_version": self.api_version,
            "plugin": self.plugin.to_dict(),
            "requires": self.requires.to_dict(),
            "exports": self.exports.to_dict(),
            "handles": list(self.handles),
            "blocked_capabilities": list(self.blocked_capabilities),
            "public_actions": [action.to_dict() for action in self.public_actions],
            "path": self.path,
        }


@dataclass
class DomainPlugin:
    manifest: PluginManifest
    semantic: ModuleType | None = None
    planner: ModuleType | None = None
    policy: ModuleType | None = None

    @property
    def domain_id(self) -> str:
        return self.manifest.id

    @property
    def supported_capabilities(self) -> tuple[str, ...]:
        return self.manifest.handles

    @property
    def blocked_capabilities(self) -> tuple[str, ...]:
        return self.manifest.blocked_capabilities

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "manifest": self.manifest.to_dict(),
            "modules": {
                "semantic": self.semantic is not None,
                "planner": self.planner is not None,
                "policy": self.policy is not None,
            },
        }


class PluginLoader:
    def __init__(self, root: str | Path = "plugins") -> None:
        self.root = Path(root)

    def discover_manifest_paths(self) -> List[Path]:
        if not self.root.exists():
            return []
        candidates: List[Path] = []
        for child in sorted(path for path in self.root.iterdir() if path.is_dir()):
            for filename in ("manifest.yaml", "manifest.yml", "manifest.json"):
                manifest_path = child / filename
                if manifest_path.exists():
                    candidates.append(manifest_path)
                    break
        return candidates

    def load_manifest(self, path: str | Path) -> PluginManifest:
        return PluginManifest.from_file(path)

    def load_plugin(self, path: str | Path) -> DomainPlugin:
        manifest = self.load_manifest(path)
        base_path = Path(manifest.path or Path(path).parent)
        return DomainPlugin(
            manifest=manifest,
            semantic=self._maybe_import(base_path / "semantic.py", f"{manifest.id}.semantic") if manifest.exports.semantic else None,
            planner=self._maybe_import(base_path / "planner.py", f"{manifest.id}.planner") if manifest.exports.planner else None,
            policy=self._maybe_import(base_path / "policy.py", f"{manifest.id}.policy") if manifest.exports.policy else None,
        )

    def load_registry(self) -> "PluginRegistry":
        registry = PluginRegistry()
        for manifest_path in self.discover_manifest_paths():
            registry.register(self.load_plugin(manifest_path))
        return registry

    def _maybe_import(self, path: Path, name: str) -> ModuleType | None:
        if not path.exists():
            return None
        safe_name = "aca_loaded_plugin_" + re.sub(r"[^a-zA-Z0-9_]", "_", name)
        spec = importlib.util.spec_from_file_location(safe_name, path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: Dict[str, DomainPlugin] = {}

    def register(self, plugin: DomainPlugin | PluginManifest) -> DomainPlugin:
        wrapped = plugin if isinstance(plugin, DomainPlugin) else DomainPlugin(manifest=plugin)
        if wrapped.domain_id in self._plugins:
            raise ValueError(f"Plugin already registered: {wrapped.domain_id}")
        self._plugins[wrapped.domain_id] = wrapped
        return wrapped

    def unregister(self, plugin_id: str) -> None:
        self._plugins.pop(plugin_id, None)

    def get(self, plugin_id: str) -> DomainPlugin | None:
        return self._plugins.get(plugin_id)

    def all(self) -> List[DomainPlugin]:
        return list(self._plugins.values())

    def plugin_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._plugins))

    def to_dict(self) -> Dict[str, Any]:
        return {plugin_id: plugin.to_dict() for plugin_id, plugin in sorted(self._plugins.items())}


class CapabilityRegistry:
    def __init__(self) -> None:
        self._capabilities: Dict[str, List[str]] = {}

    @classmethod
    def from_plugins(cls, registry: PluginRegistry) -> "CapabilityRegistry":
        capabilities = cls()
        for plugin in registry.all():
            capabilities.register_plugin(plugin.manifest)
        return capabilities

    def register_plugin(self, manifest: PluginManifest) -> None:
        for capability in manifest.handles:
            if capability in manifest.blocked_capabilities:
                continue
            self._capabilities.setdefault(capability, [])
            if manifest.id not in self._capabilities[capability]:
                self._capabilities[capability].append(manifest.id)

    def providers_for(self, capability: str) -> tuple[str, ...]:
        return tuple(self._capabilities.get(capability, ()))

    def capabilities(self) -> tuple[str, ...]:
        return tuple(sorted(self._capabilities))

    def to_dict(self) -> Dict[str, List[str]]:
        return {capability: sorted(providers) for capability, providers in sorted(self._capabilities.items())}


@dataclass(frozen=True)
class CorePolicy:
    allow_unknown_text: bool = True
    fallback_capability: str = _DEFAULT_FALLBACK_CAPABILITY

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow_unknown_text": self.allow_unknown_text,
            "fallback_capability": self.fallback_capability,
        }


@dataclass(frozen=True)
class DomainPolicy:
    plugin_id: str
    blocked_capabilities: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_manifest(cls, manifest: PluginManifest) -> "DomainPolicy":
        return cls(plugin_id=manifest.id, blocked_capabilities=manifest.blocked_capabilities)

    def allows(self, capability: str) -> bool:
        return capability not in self.blocked_capabilities

    def to_dict(self) -> Dict[str, Any]:
        return {"plugin_id": self.plugin_id, "blocked_capabilities": list(self.blocked_capabilities)}


class PolicyEngine:
    def __init__(self, core_policy: CorePolicy | None = None) -> None:
        self.core_policy = core_policy or CorePolicy()
        self._domain_policies: Dict[str, DomainPolicy] = {}

    def register_manifest(self, manifest: PluginManifest) -> None:
        self._domain_policies[manifest.id] = DomainPolicy.from_manifest(manifest)

    def allows(self, plugin_id: str, capability: str) -> bool:
        policy = self._domain_policies.get(plugin_id)
        return True if policy is None else policy.allows(capability)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "core_policy": self.core_policy.to_dict(),
            "domain_policies": {key: policy.to_dict() for key, policy in sorted(self._domain_policies.items())},
        }


@dataclass(frozen=True)
class RouteDecision:
    selected_plugin_id: str | None
    selected_capability: str | None
    score: int
    reason: str
    candidates: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_plugin_id": self.selected_plugin_id,
            "selected_capability": self.selected_capability,
            "score": self.score,
            "reason": self.reason,
            "candidates": list(self.candidates),
        }


@dataclass(frozen=True)
class PluginExecutionContext:
    conversation_id: str
    request_id: str
    plugin_id: str
    capability: str
    message: str
    public_action_id: str | None
    conversation_mode: str
    state: Mapping[str, Any]
    route_decision: Mapping[str, Any]
    manifest: Mapping[str, Any]
    blocked_capabilities: tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "request_id": self.request_id,
            "plugin_id": self.plugin_id,
            "capability": self.capability,
            "message": self.message,
            "public_action_id": self.public_action_id,
            "conversation_mode": self.conversation_mode,
            "state": dict(self.state),
            "route_decision": dict(self.route_decision),
            "manifest": dict(self.manifest),
            "blocked_capabilities": list(self.blocked_capabilities),
        }


class CapabilityRouter:
    def __init__(
        self,
        plugin_registry: PluginRegistry,
        capability_registry: CapabilityRegistry,
        policy_engine: PolicyEngine | None = None,
        fallback_capability: str = _DEFAULT_FALLBACK_CAPABILITY,
    ) -> None:
        self.plugin_registry = plugin_registry
        self.capability_registry = capability_registry
        self.policy_engine = policy_engine or PolicyEngine()
        self.fallback_capability = fallback_capability

    def route(self, *, requested_capability: str | None = None, text: str = "") -> RouteDecision:
        if requested_capability:
            providers = tuple(
                plugin_id
                for plugin_id in self.capability_registry.providers_for(requested_capability)
                if self.policy_engine.allows(plugin_id, requested_capability)
            )
            if providers:
                return RouteDecision(providers[0], requested_capability, 100, "requested_capability", providers)

        text_decision = self._route_by_text(text)
        if text_decision.selected_plugin_id:
            return text_decision

        providers = tuple(
            plugin_id
            for plugin_id in self.capability_registry.providers_for(self.fallback_capability)
            if self.policy_engine.allows(plugin_id, self.fallback_capability)
        )
        if providers:
            return RouteDecision(providers[0], self.fallback_capability, 1, "fallback", providers)
        return RouteDecision(None, None, 0, "no_capability", ())

    def _route_by_text(self, text: str) -> RouteDecision:
        normalized = _normalize(text)
        if not normalized:
            return RouteDecision(None, None, 0, "empty_text", ())

        best: tuple[int, str, str] | None = None
        for plugin in self.plugin_registry.all():
            semantic_candidate = self._semantic_candidate(plugin, text)
            if semantic_candidate is not None:
                candidate = semantic_candidate
                if best is None or candidate > best:
                    best = candidate
            searchable = _normalize(" ".join([plugin.domain_id, plugin.manifest.plugin.display_name, *plugin.supported_capabilities]))
            score = sum(1 for token in normalized.split() if token and token in searchable)
            for capability in plugin.supported_capabilities:
                capability_words = _normalize(capability).split()
                score += sum(3 for word in capability_words if word and word in normalized)
                if score > 0 and self.policy_engine.allows(plugin.domain_id, capability):
                    candidate = (score, plugin.domain_id, capability)
                    if best is None or candidate > best:
                        best = candidate
        if best is None:
            return RouteDecision(None, None, 0, "no_text_match", ())
        score, plugin_id, capability = best
        return RouteDecision(plugin_id, capability, score, "text_match", (plugin_id,))

    def _semantic_candidate(self, plugin: DomainPlugin, text: str) -> tuple[int, str, str] | None:
        if plugin.domain_id == self.fallback_capability:
            return None
        if plugin.semantic is None:
            return None
        analyze = getattr(plugin.semantic, "analyze", None)
        if not callable(analyze):
            return None
        try:
            output = analyze(text)
        except TypeError:
            return None
        if not isinstance(output, Mapping):
            return None
        capability = str(output.get("capability") or output.get("intent") or "")
        if capability not in plugin.supported_capabilities:
            return None
        if not self.policy_engine.allows(plugin.domain_id, capability):
            return None
        try:
            confidence = float(output.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        return (max(2, int(confidence * 100)) + 25, plugin.domain_id, capability)


@dataclass(frozen=True)
class PluginState:
    conversation_id: str
    plugin_id: str
    capability: str
    version: int = 1
    data: Mapping[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.conversation_id}:{self.plugin_id}:{self.capability}"

    def evolve(self, **changes: Any) -> "PluginState":
        data = dict(self.data)
        data.update(changes)
        return PluginState(
            conversation_id=self.conversation_id,
            plugin_id=self.plugin_id,
            capability=self.capability,
            version=self.version + 1,
            data=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "plugin_id": self.plugin_id,
            "capability": self.capability,
            "version": self.version,
            "key": self.key,
            "data": dict(self.data),
        }


class PluginStateStore:
    def __init__(self) -> None:
        self._states: Dict[str, PluginState] = {}

    def get_or_create(self, conversation_id: str, plugin_id: str, capability: str) -> PluginState:
        state = PluginState(conversation_id=conversation_id, plugin_id=plugin_id, capability=capability)
        return self._states.setdefault(state.key, state)

    def update(self, state: PluginState, **changes: Any) -> PluginState:
        evolved = state.evolve(**changes)
        self._states[evolved.key] = evolved
        return evolved

    def by_conversation(self, conversation_id: str) -> List[PluginState]:
        prefix = f"{conversation_id}:"
        return [state for key, state in sorted(self._states.items()) if key.startswith(prefix)]


class PluginTraceRecorder:
    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []

    def record(
        self,
        event_type: str,
        *,
        conversation_id: str | None = None,
        request_id: str | None = None,
        plugin_id: str | None = None,
        capability: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        event = {
            "index": len(self._events) + 1,
            "trace_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "conversation_id": conversation_id,
            "request_id": request_id,
            "event_type": event_type,
            "plugin_id": plugin_id,
            "capability": capability,
            "payload": _safe_payload(payload or {}),
        }
        self._events.append(event)
        return event

    def events(self) -> List[Dict[str, Any]]:
        return [dict(event) for event in self._events]

    def to_dict(self, *, conversation_id: str | None = None, request_id: str | None = None) -> Dict[str, Any]:
        events = self.events()
        if conversation_id is not None:
            events = [event for event in events if event.get("conversation_id") == conversation_id]
        if request_id is not None:
            events = [event for event in events if event.get("request_id") == request_id]
        active = next((event for event in reversed(events) if event.get("plugin_id")), None)
        return {
            "active_plugin_id": active.get("plugin_id") if active else None,
            "active_capability": active.get("capability") if active else None,
            "events": events,
        }


class EvalHookRegistry:
    def __init__(self) -> None:
        self._hooks: Dict[str, Dict[str, Callable[..., Any] | None]] = {}

    def register(self, plugin_id: str, hook_name: str, hook: Callable[..., Any] | None = None) -> None:
        self._hooks.setdefault(plugin_id, {})[hook_name] = hook

    def register_manifest(self, manifest: PluginManifest) -> None:
        if manifest.exports.evals:
            self.register(manifest.id, "plugin.eval")

    def hooks_for(self, plugin_id: str) -> tuple[str, ...]:
        return tuple(sorted(self._hooks.get(plugin_id, {})))

    def to_dict(self) -> Dict[str, List[str]]:
        return {plugin_id: sorted(hooks) for plugin_id, hooks in sorted(self._hooks.items())}


@dataclass(frozen=True)
class PluginRuntimeResult:
    route: RouteDecision
    state: PluginState | None
    trace: Mapping[str, Any]
    policy: Mapping[str, Any]
    semantic: Mapping[str, Any] = field(default_factory=dict)
    policy_decision: Mapping[str, Any] = field(default_factory=dict)
    plan: Mapping[str, Any] = field(default_factory=dict)
    hook_execution: Mapping[str, bool] = field(default_factory=dict)
    request_id: str | None = None
    conversation_mode: str = "client_support"
    public_action_id: str | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route": self.route.to_dict(),
            "state": self.state.to_dict() if self.state else None,
            "trace": dict(self.trace),
            "policy": dict(self.policy),
            "semantic": dict(self.semantic),
            "policy_decision": dict(self.policy_decision),
            "plan": dict(self.plan),
            "hook_execution": dict(self.hook_execution),
            "request_id": self.request_id,
            "conversation_mode": self.conversation_mode,
            "public_action_id": self.public_action_id,
        }


class PluginRuntime:
    def __init__(
        self,
        plugin_registry: PluginRegistry,
        capability_registry: CapabilityRegistry | None = None,
        policy_engine: PolicyEngine | None = None,
        state_store: PluginStateStore | None = None,
        trace_recorder: PluginTraceRecorder | None = None,
        eval_hooks: EvalHookRegistry | None = None,
    ) -> None:
        self.plugin_registry = plugin_registry
        self.capability_registry = capability_registry or CapabilityRegistry.from_plugins(plugin_registry)
        self.policy_engine = policy_engine or PolicyEngine()
        self.state_store = state_store or PluginStateStore()
        self.trace_recorder = trace_recorder or PluginTraceRecorder()
        self.eval_hooks = eval_hooks or EvalHookRegistry()
        for plugin in plugin_registry.all():
            self.policy_engine.register_manifest(plugin.manifest)
            self.eval_hooks.register_manifest(plugin.manifest)
        self.router = CapabilityRouter(
            plugin_registry=self.plugin_registry,
            capability_registry=self.capability_registry,
            policy_engine=self.policy_engine,
        )

    @classmethod
    def from_path(cls, root: str | Path = "plugins") -> "PluginRuntime":
        registry = PluginLoader(root).load_registry()
        return cls(registry)

    def process(
        self,
        text: str,
        *,
        conversation_id: str = "default",
        requested_capability: str | None = None,
        public_action_id: str | None = None,
        conversation_mode: str = "client_support",
        request_id: str | None = None,
    ) -> PluginRuntimeResult:
        request_id = request_id or str(uuid.uuid4())
        route = self.router.route(requested_capability=requested_capability, text=text)
        self.trace_recorder.record(
            "route.selected",
            conversation_id=conversation_id,
            request_id=request_id,
            plugin_id=route.selected_plugin_id,
            capability=route.selected_capability,
            payload=route.to_dict(),
        )
        if route.selected_plugin_id is None or route.selected_capability is None:
            self.trace_recorder.record(
                "route.unresolved",
                conversation_id=conversation_id,
                request_id=request_id,
                payload={"text_length": len(text)},
            )
            return PluginRuntimeResult(
                route=route,
                state=None,
                trace=self.trace_recorder.to_dict(conversation_id=conversation_id, request_id=request_id),
                policy=self.policy_engine.to_dict(),
                request_id=request_id,
                conversation_mode=conversation_mode,
                public_action_id=public_action_id,
            )

        state = self.state_store.get_or_create(conversation_id, route.selected_plugin_id, route.selected_capability)
        plugin = self.plugin_registry.get(route.selected_plugin_id)
        context = PluginExecutionContext(
            conversation_id=conversation_id,
            request_id=request_id,
            plugin_id=route.selected_plugin_id,
            capability=route.selected_capability,
            message=text,
            public_action_id=public_action_id,
            conversation_mode=conversation_mode,
            state=state.to_dict(),
            route_decision=route.to_dict(),
            manifest=plugin.manifest.to_dict() if plugin else {},
            blocked_capabilities=plugin.blocked_capabilities if plugin else (),
        )
        semantic, semantic_ran = self._run_semantic(plugin, text, context)
        policy_decision, policy_ran = self._run_policy(plugin, context)
        plan, planner_ran = self._run_planner(plugin, context)
        for name, ran, payload in (
            ("semantic", semantic_ran, semantic),
            ("policy", policy_ran, policy_decision),
            ("planner", planner_ran, plan),
        ):
            self.trace_recorder.record(
                f"plugin.{name}.{'executed' if ran else 'missing'}",
                conversation_id=conversation_id,
                request_id=request_id,
                plugin_id=route.selected_plugin_id,
                capability=route.selected_capability,
                payload=payload,
            )
        updated = self.state_store.update(
            state,
            last_input=text,
            active_plugin_id=route.selected_plugin_id,
            active_capability=route.selected_capability,
            semantic=semantic,
            policy_decision=policy_decision,
            plan=plan,
            public_action_id=public_action_id,
            conversation_mode=conversation_mode,
        )
        self.trace_recorder.record(
            "state.updated",
            conversation_id=conversation_id,
            request_id=request_id,
            plugin_id=updated.plugin_id,
            capability=updated.capability,
            payload={"state_key": updated.key, "version": updated.version},
        )
        for hook_name in self.eval_hooks.hooks_for(route.selected_plugin_id):
            self.trace_recorder.record(
                "eval.hook.available",
                conversation_id=conversation_id,
                request_id=request_id,
                plugin_id=route.selected_plugin_id,
                capability=route.selected_capability,
                payload={"hook": hook_name},
            )
        return PluginRuntimeResult(
            route=route,
            state=updated,
            trace=self.trace_recorder.to_dict(conversation_id=conversation_id, request_id=request_id),
            policy=self.policy_engine.to_dict(),
            semantic=semantic,
            policy_decision=policy_decision,
            plan=plan,
            hook_execution={"semantic": semantic_ran, "policy": policy_ran, "planner": planner_ran},
            request_id=request_id,
            conversation_mode=conversation_mode,
            public_action_id=public_action_id,
        )

    def _run_semantic(self, plugin: DomainPlugin | None, text: str, context: PluginExecutionContext) -> tuple[Dict[str, Any], bool]:
        if plugin is None or plugin.semantic is None:
            return {}, False
        analyze = getattr(plugin.semantic, "analyze", None)
        if not callable(analyze):
            return {}, False
        try:
            result = analyze(text, context)
        except TypeError:
            result = analyze(text)
        return dict(result or {}), True

    def _run_policy(self, plugin: DomainPlugin | None, context: PluginExecutionContext) -> tuple[Dict[str, Any], bool]:
        if plugin is None or plugin.policy is None:
            return {"allowed": True}, False
        authorize = getattr(plugin.policy, "authorize", None)
        evaluate = getattr(plugin.policy, "evaluate", None)
        if callable(authorize):
            return dict(authorize(context) or {}), True
        if callable(evaluate):
            return dict(evaluate(context.to_dict()) or {}), True
        return {"allowed": True}, False

    def _run_planner(self, plugin: DomainPlugin | None, context: PluginExecutionContext) -> tuple[Dict[str, Any], bool]:
        if plugin is None or plugin.planner is None:
            return {}, False
        plan = getattr(plugin.planner, "plan", None)
        if not callable(plan):
            return {}, False
        return dict(plan(context) or {}), True


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _safe_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    sensitive_terms = ("prompt", "secret", "token", "password", "credential")

    def clean(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                str(key): ("<redacted>" if any(term in str(key).lower() for term in sensitive_terms) else clean(item))
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, tuple):
            return [clean(item) for item in value]
        return value

    return dict(clean(payload))
