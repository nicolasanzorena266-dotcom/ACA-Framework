from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Protocol

from aca_os.execution_trace import sanitize
from aca_os.studio_runtime_binding import build_studio_runtime_binding


class StudioRequester(Protocol):
    def __call__(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | str | None = None,
        body: Mapping[str, Any] | bytes | str | None = None,
    ) -> Any:
        ...


@dataclass(frozen=True)
class StudioAPIResource:
    """One real Runtime API resource consumed by ACA Studio."""

    id: str
    method: str
    path: str
    capability: str
    purpose: str
    read_only: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "method": self.method,
            "path": self.path,
            "capability": self.capability,
            "purpose": self.purpose,
            "read_only": self.read_only,
        }


@dataclass(frozen=True)
class StudioAPIState:
    """Studio-facing state assembled only through Runtime Interface calls."""

    contract: str
    status: Dict[str, Any]
    studio: Dict[str, Any]
    metrics: Dict[str, Any]
    components: Dict[str, Any]
    plugins: Dict[str, Any]
    domain_packs: Dict[str, Any]
    domain_context: Dict[str, Any]
    binding: Dict[str, Any]
    resources: list[StudioAPIResource] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "contract": self.contract,
                "status": self.status,
                "studio": self.studio,
                "metrics": self.metrics,
                "components": self.components,
                "plugins": self.plugins,
                "domain_packs": self.domain_packs,
                "domain_context": self.domain_context,
                "binding": self.binding,
                "resources": [resource.to_dict() for resource in self.resources],
                "metadata": self.metadata,
            }
        )


STUDIO_API_RESOURCES: tuple[StudioAPIResource, ...] = (
    StudioAPIResource("bootstrap", "GET", "/studio/bootstrap", "studio.bootstrap", "Load Studio API wiring."),
    StudioAPIResource("state", "GET", "/studio/state", "studio.state.read", "Read Studio dashboard state."),
    StudioAPIResource("runtime_status", "GET", "/runtime/status", "runtime.status", "Read Runtime status."),
    StudioAPIResource("runtime_studio", "GET", "/runtime/studio", "studio.read", "Read Runtime-backed Studio view."),
    StudioAPIResource("metrics", "GET", "/runtime/metrics", "metrics.read", "Read Runtime metrics."),
    StudioAPIResource("components", "GET", "/runtime/components", "component.list", "Read Component Registry."),
    StudioAPIResource("plugins", "GET", "/runtime/plugins", "plugin.list", "Read Plugin Registry."),
    StudioAPIResource("domain_packs", "GET", "/runtime/domain-packs", "domain_pack.list", "Read loaded Domain Packs."),
    StudioAPIResource("domain_context", "GET", "/runtime/domain-context", "domain_pack.context.read", "Read active Domain Pack context."),
    StudioAPIResource("binding", "GET", "/studio/binding", "studio.runtime.binding", "Read bound Studio Runtime dashboard."),
    StudioAPIResource("binding_run", "POST", "/studio/binding/run", "studio.runtime.binding.run", "Run one message and return refreshed binding.", False),
    StudioAPIResource("run", "POST", "/studio/run", "studio.runtime.run", "Run one message and refresh Studio state.", False),
    StudioAPIResource("replay", "POST", "/studio/replay", "studio.session.replay", "Replay one saved session into Studio.", False),
)


class StudioAPIClient:
    """Client contract used by Studio shells.

    The client calls the Runtime Interface. It does not construct runtimes,
    access components, or own business behavior.
    """

    def __init__(self, requester: StudioRequester, *, base_url: str = "") -> None:
        self.requester = requester
        self.base_url = base_url.rstrip("/")

    def bootstrap(self) -> Dict[str, Any]:
        health = self._request("GET", "/health")
        studio = self._request("GET", "/runtime/studio")
        return build_studio_bootstrap(
            base_url=self.base_url or "/",
            runtime_health=health,
            studio_view=studio,
        )

    def read_state(self, *, memory_path: str | None = None) -> Dict[str, Any]:
        query = {"memory_path": memory_path} if memory_path else None
        status = self._request("GET", "/runtime/status", query=query)
        studio = self._request("GET", "/runtime/studio", query=query)
        metrics = self._request("GET", "/runtime/metrics", query=query)
        components = self._request("GET", "/runtime/components", query=query)
        plugins = self._request("GET", "/runtime/plugins", query=query)
        domain_packs = self._request("GET", "/runtime/domain-packs", query=query)
        domain_context = self._request("GET", "/runtime/domain-context", query=query)
        binding = build_studio_runtime_binding(
            status=status,
            metrics=metrics,
            components=components,
            plugins=plugins,
            domain_packs=domain_packs,
            domain_context=domain_context,
            endpoints={"resources": [resource.to_dict() for resource in STUDIO_API_RESOURCES]},
            studio=studio,
        )
        state = StudioAPIState(
            contract="studio_api_state.v1",
            status=status,
            studio=studio,
            metrics=metrics,
            components=components,
            plugins=plugins,
            domain_packs=domain_packs,
            domain_context=domain_context,
            binding=binding,
            resources=list(STUDIO_API_RESOURCES),
            metadata={"source": "runtime_rest_api", "read_only_projection": True},
        )
        return state.to_dict()

    def run_message(
        self,
        *,
        message: str,
        conversation_id: str = "studio",
        memory_path: str | None = None,
    ) -> Dict[str, Any]:
        if not message:
            raise ValueError("message is required.")
        return self._request(
            "POST",
            "/runtime/events",
            body={
                "event_type": "user_message",
                "payload": message,
                "metadata": {"conversation_id": conversation_id},
                "memory_path": memory_path,
                "include_trace": True,
                "include_introspection": True,
                "include_studio": True,
            },
        )

    def replay_session(self, *, path: str, memory_path: str | None = None) -> Dict[str, Any]:
        if not path:
            raise ValueError("path is required.")
        return self._request("POST", "/sessions/replay", body={"path": path, "memory_path": memory_path})

    def _request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | str | None = None,
        body: Mapping[str, Any] | bytes | str | None = None,
    ) -> Dict[str, Any]:
        response = self.requester(method, path, query=query, body=body)
        status_code = getattr(response, "status_code", 200)
        payload = getattr(response, "payload", response)
        if not isinstance(payload, Mapping):
            raise ValueError(f"Studio API requester returned non-object payload for {method} {path}.")
        if int(status_code) >= 400:
            error = dict(payload).get("error", {})
            message = error.get("message") if isinstance(error, Mapping) else None
            raise ValueError(message or f"Studio API request failed: {method} {path}.")
        return sanitize(dict(payload))


def build_studio_bootstrap(
    *,
    base_url: str = "/",
    runtime_health: Mapping[str, Any] | None = None,
    studio_view: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return the stable Studio boot contract.

    This is UI wiring only. Runtime data is passed in from Runtime Interface
    responses and remains the source of truth.
    """
    health = dict(runtime_health or {})
    studio = dict(studio_view or {})
    return sanitize(
        {
            "contract": "studio_api_integration.v1",
            "base_url": base_url or "/",
            "runtime_status": health.get("runtime_status") or health.get("status"),
            "runtime_id": health.get("runtime_id") or studio.get("runtime_id"),
            "read_only": True,
            "resources": [resource.to_dict() for resource in STUDIO_API_RESOURCES],
            "initial_view": studio,
            "metadata": {
                "source": "runtime_rest_api",
                "interface": "aca_studio",
                "business_logic": "runtime_only",
            },
        }
    )
