from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from aca_kernel.core.events import Event
from sdk.factory import build_galicia_runtime, process_message

RuntimeFactory = Callable[..., Any]


@dataclass(frozen=True)
class RuntimeEndpoint:
    """Stable Runtime API endpoint contract independent from transports."""

    method: str
    path: str
    description: str
    capability: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "method": self.method,
            "path": self.path,
            "description": self.description,
            "capability": self.capability,
        }


class RuntimeEndpointAPI:
    """Transport-neutral Runtime endpoint surface.

    REST, CLI, Studio and future MCP adapters should call this boundary instead
    of reaching into runtime internals. The class normalizes endpoint inputs only;
    all behavior stays owned by ACAOSRuntime and SDK factories.
    """

    endpoints = (
        RuntimeEndpoint("GET", "/health", "Return adapter and Runtime health.", "runtime.health"),
        RuntimeEndpoint("GET", "/runtime/status", "Return Runtime status summary.", "runtime.status"),
        RuntimeEndpoint("GET", "/runtime/components", "List registered Runtime components.", "component.list"),
        RuntimeEndpoint("GET", "/runtime/components/{name}", "Return one registered component descriptor.", "component.read"),
        RuntimeEndpoint("GET", "/runtime/plugins", "List loaded plugins, optionally loading a plugin root first.", "plugin.list"),
        RuntimeEndpoint("POST", "/runtime/plugins/load", "Load plugins from a plugin root.", "plugin.load"),
        RuntimeEndpoint("GET", "/runtime/plugin-lifecycle", "Return plugin lifecycle snapshot.", "plugin.lifecycle.read"),
        RuntimeEndpoint("POST", "/runtime/plugin-lifecycle", "Apply a plugin lifecycle transition.", "plugin.lifecycle.transition"),
        RuntimeEndpoint("GET", "/runtime/metrics", "Return current Runtime metrics.", "metrics.read"),
        RuntimeEndpoint("GET", "/runtime/introspection", "Return Runtime introspection snapshot.", "introspection.read"),
        RuntimeEndpoint("GET", "/runtime/studio", "Return Studio-ready Runtime view.", "studio.read"),
        RuntimeEndpoint("POST", "/runtime/run", "Execute one Runtime message.", "runtime.run"),
        RuntimeEndpoint("POST", "/runtime/events", "Process one generic Runtime event.", "runtime.event.process"),
        RuntimeEndpoint("POST", "/runtime/trace", "Execute one Runtime message or event and return trace.", "trace.read"),
        RuntimeEndpoint("POST", "/sessions/save", "Execute one message and save the execution session.", "session.save"),
        RuntimeEndpoint("POST", "/sessions/replay", "Replay a persisted execution session.", "session.replay"),
    )

    def __init__(self, runtime_factory: RuntimeFactory = build_galicia_runtime) -> None:
        self.runtime_factory = runtime_factory

    def catalog(self) -> Dict[str, Any]:
        endpoints = [endpoint.to_dict() for endpoint in self.endpoints]
        return {
            "contract": "runtime_endpoints.v1",
            "endpoint_count": len(endpoints),
            "endpoints": endpoints,
        }

    def health(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        status = self.status(memory_path=memory_path)
        return {
            "status": "ok",
            "adapter": "runtime-api-endpoints",
            "runtime_status": status["status"],
            "runtime_id": status["runtime_id"],
            **self.catalog(),
        }

    def status(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        snapshot = runtime.inspect_runtime().to_dict()
        plugins = runtime.export_plugins(format="dict")
        return {
            "status": snapshot["status"],
            "runtime_id": snapshot["runtime_id"],
            "component_count": len(snapshot["components"]),
            "plugin_count": plugins["plugin_count"],
            "trace_count": snapshot["metrics"]["trace_count"],
        }

    def components(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.export_components(format="dict")

    def component(self, name: str, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        if not name:
            raise ValueError("component name is required.")
        snapshot = self.components(memory_path=memory_path)
        for descriptor in snapshot["components"]:
            if descriptor["name"] == name:
                return {"component": descriptor}
        raise KeyError(f"Component not found: {name}")

    def plugins(
        self,
        *,
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        if root:
            runtime.load_plugins(str(root), strict=strict)
        return runtime.export_plugins(format="dict")

    def load_plugins(
        self,
        *,
        root: str | Path,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        if not root:
            raise ValueError("root is required.")
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.load_plugins(str(root), strict=strict)

    def plugin_lifecycle(
        self,
        *,
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        if root:
            runtime.load_plugins(str(root), strict=strict)
        return runtime.export_plugin_lifecycle(format="dict")

    def transition_plugin(
        self,
        *,
        plugin_name: str,
        action: str,
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        if not plugin_name:
            raise ValueError("plugin_name is required.")
        if not action:
            raise ValueError("action is required.")
        runtime = self.runtime_factory(memory_path=memory_path)
        if root:
            runtime.load_plugins(str(root), strict=strict)
        transitions = {
            "initialize": runtime.initialize_plugin,
            "activate": runtime.activate_plugin,
            "pause": runtime.pause_plugin,
            "stop": runtime.stop_plugin,
            "unload": runtime.unload_plugin,
        }
        handler = transitions.get(action)
        if handler is None:
            raise ValueError(f"Unsupported plugin lifecycle action: {action}.")
        return {"plugin": handler(plugin_name), "lifecycle": runtime.export_plugin_lifecycle(format="dict")}

    def metrics(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.export_metrics(format="dict")

    def introspection(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.export_introspection(format="dict")

    def studio(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.export_studio(format="dict")

    def run_message(
        self,
        *,
        message: str,
        conversation_id: str = "rest",
        memory_path: str | Path | None = None,
        include_events: bool = False,
        include_trace: bool = False,
        include_introspection: bool = False,
        include_studio: bool = False,
        save_session_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        if not message:
            raise ValueError("message is required.")
        result = process_message(
            message=message,
            conversation_id=conversation_id,
            memory_path=memory_path,
            include_runtime_events=include_events,
            include_introspection=include_introspection,
            include_studio=include_studio,
            save_session_path=save_session_path,
        )
        if not include_trace:
            result.pop("execution_trace", None)
        return result

    def process_event(
        self,
        *,
        event_type: str,
        payload: Any = None,
        metadata: Mapping[str, Any] | None = None,
        memory_path: str | Path | None = None,
        include_trace: bool = False,
        include_introspection: bool = False,
        include_studio: bool = False,
        save_session_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        if not event_type:
            raise ValueError("event_type is required.")
        runtime = self.runtime_factory(memory_path=memory_path)
        output = runtime.process_output(Event(type=event_type, payload=payload, metadata=dict(metadata or {})))
        result = output.to_dict()
        if include_trace:
            result["execution_trace"] = runtime.export_trace(format="dict")
        if include_introspection:
            result["introspection"] = runtime.export_introspection(format="dict")
        if include_studio:
            result["studio"] = runtime.export_studio(format="dict")
        if save_session_path:
            result["session_path"] = runtime.save_last_session(str(save_session_path))
        return result

    def trace(
        self,
        *,
        message: str | None = None,
        conversation_id: str = "rest",
        event_type: str | None = None,
        payload: Any = None,
        metadata: Mapping[str, Any] | None = None,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        if event_type:
            event = Event(type=event_type, payload=payload, metadata=dict(metadata or {}))
        else:
            if not message:
                raise ValueError("message is required.")
            event = Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id})
        runtime.process_output(event)
        return runtime.export_trace(format="dict")

    def save_session(
        self,
        *,
        message: str,
        path: str | Path,
        conversation_id: str = "rest",
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        if not message:
            raise ValueError("message is required.")
        if not path:
            raise ValueError("path is required.")
        runtime = self.runtime_factory(memory_path=memory_path)
        runtime.process_output(Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id}))
        saved_path = runtime.save_last_session(str(path))
        session = runtime.last_session()
        return {"status": "written", "path": saved_path, "session": session.summary() if session else {}}

    def replay_session(self, *, path: str | Path, memory_path: str | Path | None = None) -> Dict[str, Any]:
        if not path:
            raise ValueError("path is required.")
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.replay_session(str(path)).to_dict()
