from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Mapping
from urllib.parse import parse_qs, unquote

from sdk.factory import build_galicia_runtime
from aca_os.runtime_api_endpoints import RuntimeEndpoint, RuntimeEndpointAPI


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


RESTEndpoint = RuntimeEndpoint


class RuntimeRESTAPI:
    """Small REST adapter over the stable Runtime endpoint API.

    This class owns HTTP-ish request normalization only. Endpoint behavior is
    delegated to RuntimeEndpointAPI, which delegates to ACAOSRuntime.
    """

    endpoints = RuntimeEndpointAPI.endpoints

    def __init__(self, runtime_factory: RuntimeFactory = build_galicia_runtime) -> None:
        self.runtime_factory = runtime_factory
        self.runtime_api = RuntimeEndpointAPI(runtime_factory=runtime_factory)

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
        segments = _segments(clean_path)

        try:
            payload = _normalize_body(body)
            memory_path = _first(params, "memory_path") or _first(params, "memory")

            if method == "GET" and clean_path == "/health":
                health = self.runtime_api.health(memory_path=memory_path)
                health["adapter"] = "runtime-rest"
                return self.ok(health)
            if method == "GET" and clean_path == "/runtime/status":
                return self.ok(self.runtime_api.status(memory_path=memory_path))
            if method == "GET" and clean_path == "/runtime/components":
                return self.ok(self.runtime_api.components(memory_path=memory_path))
            if method == "GET" and len(segments) == 3 and segments[:2] == ["runtime", "components"]:
                return self.ok(self.runtime_api.component(unquote(segments[2]), memory_path=memory_path))
            if method == "GET" and clean_path == "/runtime/plugins":
                return self.ok(
                    self.runtime_api.plugins(
                        root=_first(params, "root"),
                        strict=_as_bool(_first(params, "strict")),
                        memory_path=memory_path,
                    )
                )
            if method == "POST" and clean_path == "/runtime/plugins/load":
                return self.ok(
                    self.runtime_api.load_plugins(
                        root=payload.get("root"),
                        strict=_as_bool(payload.get("strict")),
                        memory_path=payload.get("memory_path") or memory_path,
                    )
                )
            if method == "GET" and clean_path == "/runtime/plugin-lifecycle":
                return self.ok(
                    self.runtime_api.plugin_lifecycle(
                        root=_first(params, "root"),
                        strict=_as_bool(_first(params, "strict")),
                        memory_path=memory_path,
                    )
                )
            if method == "POST" and clean_path == "/runtime/plugin-lifecycle":
                return self.ok(
                    self.runtime_api.transition_plugin(
                        plugin_name=payload.get("plugin_name") or payload.get("name"),
                        action=payload.get("action"),
                        root=payload.get("root"),
                        strict=_as_bool(payload.get("strict")),
                        memory_path=payload.get("memory_path") or memory_path,
                    )
                )
            if method == "GET" and clean_path == "/runtime/domain-packs":
                return self.ok(
                    self.runtime_api.domain_packs(
                        root=_first(params, "root"),
                        strict=_as_bool(_first(params, "strict")),
                        memory_path=memory_path,
                    )
                )
            if method == "GET" and len(segments) == 3 and segments[:2] == ["runtime", "domain-packs"]:
                return self.ok(
                    self.runtime_api.domain_pack(
                        unquote(segments[2]),
                        root=_first(params, "root"),
                        strict=_as_bool(_first(params, "strict")),
                        memory_path=memory_path,
                    )
                )
            if method == "POST" and clean_path == "/runtime/domain-packs/load":
                return self.ok(
                    self.runtime_api.load_domain_packs(
                        root=payload.get("root"),
                        strict=_as_bool(payload.get("strict")),
                        memory_path=payload.get("memory_path") or memory_path,
                    )
                )
            if method == "GET" and clean_path == "/runtime/domain-context":
                return self.ok(
                    self.runtime_api.domain_context(
                        root=_first(params, "root"),
                        strict=_as_bool(_first(params, "strict")),
                        memory_path=memory_path,
                    )
                )
            if method == "GET" and clean_path == "/runtime/metrics":
                return self.ok(self.runtime_api.metrics(memory_path=memory_path))
            if method == "GET" and clean_path == "/runtime/introspection":
                return self.ok(self.runtime_api.introspection(memory_path=memory_path))
            if method == "GET" and clean_path == "/runtime/studio":
                return self.ok(self.runtime_api.studio(memory_path=memory_path))
            if method == "GET" and clean_path == "/studio/bootstrap":
                return self.ok(
                    self.runtime_api.studio_bootstrap(
                        base_url=_first(params, "base_url") or "/",
                        memory_path=memory_path,
                    )
                )
            if method == "GET" and clean_path == "/studio/state":
                return self.ok(self.runtime_api.studio_state(memory_path=memory_path))
            if method == "GET" and clean_path == "/studio/binding":
                return self.ok(
                    self.runtime_api.studio_binding(
                        root=_first(params, "root"),
                        strict=_as_bool(_first(params, "strict")),
                        memory_path=memory_path,
                    )
                )
            if method == "POST" and clean_path == "/studio/run":
                return self.ok(
                    self.runtime_api.studio_run(
                        message=payload.get("message"),
                        conversation_id=payload.get("conversation_id") or "studio",
                        memory_path=payload.get("memory_path") or memory_path,
                    )
                )
            if method == "POST" and clean_path == "/studio/binding/run":
                return self.ok(
                    self.runtime_api.studio_binding_run(
                        message=payload.get("message"),
                        conversation_id=payload.get("conversation_id") or "studio",
                        root=payload.get("root"),
                        strict=_as_bool(payload.get("strict")),
                        memory_path=payload.get("memory_path") or memory_path,
                    )
                )
            if method == "POST" and clean_path == "/studio/replay":
                return self.ok(
                    self.runtime_api.studio_replay(
                        path=payload.get("path"),
                        memory_path=payload.get("memory_path") or memory_path,
                    )
                )
            if method == "POST" and clean_path == "/runtime/run":
                return self.ok(self.runtime_api.run_message(**payload))
            if method == "POST" and clean_path == "/runtime/events":
                return self.ok(
                    self.runtime_api.process_event(
                        event_type=payload.get("event_type") or payload.get("type"),
                        payload=payload.get("payload"),
                        metadata=payload.get("metadata"),
                        memory_path=payload.get("memory_path"),
                        include_trace=_as_bool(payload.get("include_trace")),
                        include_introspection=_as_bool(payload.get("include_introspection")),
                        include_studio=_as_bool(payload.get("include_studio")),
                        save_session_path=payload.get("save_session_path"),
                    )
                )
            if method == "POST" and clean_path == "/runtime/trace":
                return self.ok(self.runtime_api.trace(**payload))
            if method == "POST" and clean_path == "/sessions/save":
                return self.ok(self.runtime_api.save_session(**payload))
            if method == "POST" and clean_path == "/sessions/replay":
                return self.ok(self.runtime_api.replay_session(**payload))
            if method == "GET" and clean_path == "/demo/human-test":
                return self.ok(self.runtime_api.human_demo_scenario())
            if method == "POST" and clean_path == "/demo/human-test":
                return self.ok(
                    self.runtime_api.run_human_demo(
                        conversation_id=payload.get("conversation_id") or "human-demo",
                        memory_path=payload.get("memory_path") or memory_path,
                        format=payload.get("format") or "dict",
                    )
                )
            return self.error(404, "not_found", f"No REST endpoint for {method} {clean_path}.")
        except KeyError as exc:
            return self.error(404, "not_found", str(exc).strip("'"))
        except ValueError as exc:
            return self.error(400, "bad_request", str(exc))
        except TypeError as exc:
            return self.error(400, "bad_request", str(exc))

    def ok(self, payload: Dict[str, Any]) -> RESTResponse:
        return RESTResponse(status_code=200, payload=payload)

    def error(self, status_code: int, code: str, message: str) -> RESTResponse:
        return RESTResponse(status_code=status_code, payload={"error": {"code": code, "message": message}})

    def health(self) -> Dict[str, Any]:
        health = self.runtime_api.health()
        health["adapter"] = "runtime-rest"
        return health

    def status(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        return self.runtime_api.status(memory_path=memory_path)

    def components(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        return self.runtime_api.components(memory_path=memory_path)

    def plugins(
        self,
        *,
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        return self.runtime_api.plugins(root=root, strict=strict, memory_path=memory_path)

    def domain_packs(
        self,
        *,
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        return self.runtime_api.domain_packs(root=root, strict=strict, memory_path=memory_path)

    def load_domain_packs(
        self,
        *,
        root: str | Path,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        return self.runtime_api.load_domain_packs(root=root, strict=strict, memory_path=memory_path)

    def domain_context(
        self,
        *,
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        return self.runtime_api.domain_context(root=root, strict=strict, memory_path=memory_path)

    def metrics(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        return self.runtime_api.metrics(memory_path=memory_path)

    def introspection(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        return self.runtime_api.introspection(memory_path=memory_path)

    def studio_bootstrap(self, *, base_url: str = "/", memory_path: str | Path | None = None) -> Dict[str, Any]:
        return self.runtime_api.studio_bootstrap(base_url=base_url, memory_path=memory_path)

    def studio_state(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        return self.runtime_api.studio_state(memory_path=memory_path)

    def studio_run(self, **payload: Any) -> Dict[str, Any]:
        return self.runtime_api.studio_run(**payload)

    def run(self, **payload: Any) -> Dict[str, Any]:
        return self.runtime_api.run_message(**payload)

    def trace(self, **payload: Any) -> Dict[str, Any]:
        return self.runtime_api.trace(**payload)

    def replay_session(self, *, path: str | Path, memory_path: str | Path | None = None) -> Dict[str, Any]:
        return self.runtime_api.replay_session(path=path, memory_path=memory_path)

    def human_demo_scenario(self) -> Dict[str, Any]:
        return self.runtime_api.human_demo_scenario()

    def run_human_demo(self, **payload: Any) -> Dict[str, Any] | str:
        return self.runtime_api.run_human_demo(**payload)


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


def _segments(path: str) -> list[str]:
    return [part for part in path.split("/") if part]
