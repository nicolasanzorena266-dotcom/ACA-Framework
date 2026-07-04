from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping
from urllib.parse import parse_qs

from aca_kernel.core.events import Event
from sdk.factory import build_galicia_runtime, process_message


RuntimeFactory = Callable[..., Any]


@dataclass(frozen=True)
class RESTResponse:
    """Transport-neutral REST response contract.

    HTTP adapters render this object. Tests and future interfaces can use it
    without starting a socket server.
    """

    status_code: int
    payload: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=lambda: {"content-type": "application/json; charset=utf-8"})

    def to_json(self) -> str:
        return json.dumps(self.payload, ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class RESTEndpoint:
    method: str
    path: str
    description: str

    def to_dict(self) -> Dict[str, str]:
        return {"method": self.method, "path": self.path, "description": self.description}


class RuntimeRESTAPI:
    """Small REST-facing runtime facade.

    This class owns request normalization only. All runtime behavior is delegated
    to ACAOSRuntime and SDK runtime factories.
    """

    endpoints = (
        RESTEndpoint("GET", "/health", "Return REST adapter and Runtime health."),
        RESTEndpoint("GET", "/runtime/status", "Return Runtime status summary."),
        RESTEndpoint("GET", "/runtime/components", "List registered Runtime components."),
        RESTEndpoint("GET", "/runtime/plugins", "List loaded plugins, optionally loading a plugin root first."),
        RESTEndpoint("GET", "/runtime/metrics", "Return current Runtime metrics."),
        RESTEndpoint("GET", "/runtime/introspection", "Return Runtime introspection snapshot."),
        RESTEndpoint("POST", "/runtime/run", "Execute one Runtime message."),
        RESTEndpoint("POST", "/runtime/trace", "Execute one Runtime message and return its execution trace."),
        RESTEndpoint("POST", "/sessions/replay", "Replay a persisted execution session."),
    )

    def __init__(self, runtime_factory: RuntimeFactory = build_galicia_runtime) -> None:
        self.runtime_factory = runtime_factory

    def route(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | str | None = None,
        body: Mapping[str, Any] | bytes | str | None = None,
    ) -> RESTResponse:
        method = method.upper()
        clean_path = path.rstrip("/") or "/"
        params = _normalize_query(query)

        try:
            payload = _normalize_body(body)
            if method == "GET" and clean_path == "/health":
                return self.ok(self.health())
            if method == "GET" and clean_path == "/runtime/status":
                return self.ok(self.status(memory_path=_first(params, "memory_path") or _first(params, "memory")))
            if method == "GET" and clean_path == "/runtime/components":
                return self.ok(self.components(memory_path=_first(params, "memory_path") or _first(params, "memory")))
            if method == "GET" and clean_path == "/runtime/plugins":
                return self.ok(
                    self.plugins(
                        root=_first(params, "root"),
                        strict=_as_bool(_first(params, "strict")),
                        memory_path=_first(params, "memory_path") or _first(params, "memory"),
                    )
                )
            if method == "GET" and clean_path == "/runtime/metrics":
                return self.ok(self.metrics(memory_path=_first(params, "memory_path") or _first(params, "memory")))
            if method == "GET" and clean_path == "/runtime/introspection":
                return self.ok(self.introspection(memory_path=_first(params, "memory_path") or _first(params, "memory")))
            if method == "POST" and clean_path == "/runtime/run":
                return self.ok(self.run(**payload))
            if method == "POST" and clean_path == "/runtime/trace":
                return self.ok(self.trace(**payload))
            if method == "POST" and clean_path == "/sessions/replay":
                return self.ok(self.replay_session(**payload))
            return self.error(404, "not_found", f"No REST endpoint for {method} {clean_path}.")
        except ValueError as exc:
            return self.error(400, "bad_request", str(exc))
        except TypeError as exc:
            return self.error(400, "bad_request", str(exc))

    def ok(self, payload: Dict[str, Any]) -> RESTResponse:
        return RESTResponse(status_code=200, payload=payload)

    def error(self, status_code: int, code: str, message: str) -> RESTResponse:
        return RESTResponse(status_code=status_code, payload={"error": {"code": code, "message": message}})

    def health(self) -> Dict[str, Any]:
        status = self.status()
        return {
            "status": "ok",
            "adapter": "runtime-rest",
            "runtime_status": status["status"],
            "runtime_id": status["runtime_id"],
            "endpoints": [endpoint.to_dict() for endpoint in self.endpoints],
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

    def metrics(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.export_metrics(format="dict")

    def introspection(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.export_introspection(format="dict")

    def run(
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
        if include_trace:
            # process_message currently returns trace only through the output payload.
            return result
        result.pop("execution_trace", None)
        return result

    def trace(
        self,
        *,
        message: str,
        conversation_id: str = "rest",
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        if not message:
            raise ValueError("message is required.")
        runtime = self.runtime_factory(memory_path=memory_path)
        runtime.process_output(_message_event(message, conversation_id))
        return runtime.export_trace(format="dict")

    def replay_session(self, *, path: str | Path, memory_path: str | Path | None = None) -> Dict[str, Any]:
        if not path:
            raise ValueError("path is required.")
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.replay_session(str(path)).to_dict()


def _message_event(message: str, conversation_id: str) -> Event:
    return Event(type="user_message", payload=message, metadata={"conversation_id": conversation_id})


def _normalize_query(query: Mapping[str, Any] | str | None) -> Dict[str, Any]:
    if query is None:
        return {}
    if isinstance(query, str):
        parsed = parse_qs(query, keep_blank_values=True)
        return {key: values[-1] if values else "" for key, values in parsed.items()}
    return dict(query)


def _normalize_body(body: Mapping[str, Any] | bytes | str | None) -> Dict[str, Any]:
    if body is None or body == b"" or body == "":
        return {}
    if isinstance(body, Mapping):
        return dict(body)
    if isinstance(body, bytes):
        body = body.decode("utf-8")
    try:
        loaded = json.loads(body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON body: {exc.msg}.") from exc
    if not isinstance(loaded, dict):
        raise ValueError("JSON body must be an object.")
    return loaded


def _first(params: Mapping[str, Any], key: str) -> Any:
    value = params.get(key)
    if isinstance(value, list):
        return value[-1] if value else None
    return value


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
