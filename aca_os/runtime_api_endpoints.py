from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping

from aca_kernel.core.events import Event
from aca_os.demo_domain_flow import DemoDomainRuntimeFlowRunner
from aca_os.deployable_web_package import build_deployable_web_package, validate_deployable_web_package
from aca_os.human_demo import HumanTestDemoRunner
from aca_os.public_web_demo import build_public_web_demo_manifest, validate_public_web_demo_readiness
from aca_os.public_demo_runtime_adapter import build_public_demo_runtime_adapter, validate_public_demo_runtime_adapter
from aca_os.public_demo_polish import build_public_demo_polish, validate_public_demo_polish
from aca_os.studio_api import StudioAPIClient, build_studio_bootstrap
from aca_os.studio_runtime_binding import build_studio_runtime_binding, build_studio_runtime_run_binding
from aca_os.studio_ux_structure import build_studio_ux_structure
from aca_os.studio_visual_design import build_studio_visual_design_system
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
        RuntimeEndpoint("GET", "/runtime/domain-packs", "List runtime-integrated Domain Packs, optionally loading a root first.", "domain_pack.list"),
        RuntimeEndpoint("GET", "/runtime/domain-packs/{name}", "Return one runtime-integrated Domain Pack.", "domain_pack.read"),
        RuntimeEndpoint("POST", "/runtime/domain-packs/load", "Load and integrate Domain Packs from a root.", "domain_pack.load"),
        RuntimeEndpoint("GET", "/runtime/domain-context", "Return runtime Domain Pack context.", "domain_pack.context.read"),
        RuntimeEndpoint("POST", "/runtime/plugins/load", "Load plugins from a plugin root.", "plugin.load"),
        RuntimeEndpoint("GET", "/runtime/plugin-lifecycle", "Return plugin lifecycle snapshot.", "plugin.lifecycle.read"),
        RuntimeEndpoint("POST", "/runtime/plugin-lifecycle", "Apply a plugin lifecycle transition.", "plugin.lifecycle.transition"),
        RuntimeEndpoint("GET", "/runtime/metrics", "Return current Runtime metrics.", "metrics.read"),
        RuntimeEndpoint("GET", "/runtime/introspection", "Return Runtime introspection snapshot.", "introspection.read"),
        RuntimeEndpoint("GET", "/runtime/studio", "Return Studio-ready Runtime view.", "studio.read"),
        RuntimeEndpoint("GET", "/studio/bootstrap", "Return Studio API bootstrap contract.", "studio.bootstrap"),
        RuntimeEndpoint("GET", "/studio/state", "Return Studio state assembled from Runtime APIs.", "studio.state.read"),
        RuntimeEndpoint("GET", "/studio/binding", "Return bound Studio Runtime dashboard state.", "studio.runtime.binding"),
        RuntimeEndpoint("GET", "/studio/ux", "Return Studio UX structure bound to Runtime API data.", "studio.ux.structure"),
        RuntimeEndpoint("GET", "/studio/design", "Return ACA Studio visual design system tokens and component styles.", "studio.visual_design.read"),
        RuntimeEndpoint("POST", "/studio/run", "Run one Studio message through Runtime APIs.", "studio.runtime.run"),
        RuntimeEndpoint("POST", "/studio/binding/run", "Run one Studio message and return refreshed binding.", "studio.runtime.binding.run"),
        RuntimeEndpoint("POST", "/studio/replay", "Replay a session through Studio API.", "studio.session.replay"),
        RuntimeEndpoint("POST", "/runtime/run", "Execute one Runtime message.", "runtime.run"),
        RuntimeEndpoint("POST", "/runtime/events", "Process one generic Runtime event.", "runtime.event.process"),
        RuntimeEndpoint("POST", "/runtime/trace", "Execute one Runtime message or event and return trace.", "trace.read"),
        RuntimeEndpoint("POST", "/sessions/save", "Execute one message and save the execution session.", "session.save"),
        RuntimeEndpoint("POST", "/sessions/replay", "Replay a persisted execution session.", "session.replay"),
        RuntimeEndpoint("GET", "/demo/human-test", "Return the human test demo scenario contract.", "demo.human_test.read"),
        RuntimeEndpoint("POST", "/demo/human-test", "Run the deterministic human test demo.", "demo.human_test.run"),
        RuntimeEndpoint("GET", "/demo/domain-flow", "Return the demo Domain Pack runtime flow scenario.", "demo.domain_flow.read"),
        RuntimeEndpoint("POST", "/demo/domain-flow", "Run one message through a loaded Domain Pack demo flow.", "demo.domain_flow.run"),
        RuntimeEndpoint("GET", "/deploy/package", "Return deployable ACA Web Runtime package contract.", "deploy.package.read"),
        RuntimeEndpoint("GET", "/deploy/validate", "Validate deployable ACA Web Runtime package files.", "deploy.package.validate"),
        RuntimeEndpoint("GET", "/public-demo/manifest", "Return public ACA Web Demo preparation manifest.", "public_demo.manifest.read"),
        RuntimeEndpoint("GET", "/public-demo/readiness", "Validate public ACA Web Demo readiness files.", "public_demo.readiness.read"),
        RuntimeEndpoint("GET", "/public-demo/runtime-adapter", "Return public demo runtime adapter contract.", "public_demo.runtime_adapter.read"),
        RuntimeEndpoint("GET", "/public-demo/runtime-adapter/validate", "Validate public demo runtime adapter contract.", "public_demo.runtime_adapter.validate"),
        RuntimeEndpoint("GET", "/public-demo/polish", "Return public ACA Studio demo polish contract.", "public_demo.polish.read"),
        RuntimeEndpoint("GET", "/public-demo/polish/validate", "Validate public ACA Studio demo polish contract.", "public_demo.polish.validate"),
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


    def domain_packs(
        self,
        *,
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        if root:
            runtime.load_domain_packs(str(root), strict=strict)
        return runtime.export_domain_packs(format="dict")

    def load_domain_packs(
        self,
        *,
        root: str | Path,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        if not root:
            raise ValueError("root is required.")
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.load_domain_packs(str(root), strict=strict)

    def domain_pack(
        self,
        name: str,
        *,
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        if not name:
            raise ValueError("domain pack name is required.")
        runtime = self.runtime_factory(memory_path=memory_path)
        if root:
            runtime.load_domain_packs(str(root), strict=strict)
        return runtime.get_domain_pack(name)

    def domain_context(
        self,
        *,
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        if root:
            runtime.load_domain_packs(str(root), strict=strict)
        return runtime.export_domain_pack_context(format="dict")

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


    def studio_bootstrap(self, *, base_url: str = "/", memory_path: str | Path | None = None) -> Dict[str, Any]:
        return build_studio_bootstrap(
            base_url=base_url,
            runtime_health=self.health(memory_path=memory_path),
            studio_view=self.studio(memory_path=memory_path),
        )

    def studio_state(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        client = StudioAPIClient(requester=self._local_requester)
        return client.read_state(memory_path=str(memory_path) if memory_path else None)


    def studio_binding(
        self,
        *,
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        return build_studio_runtime_binding(
            status=self.status(memory_path=memory_path),
            metrics=self.metrics(memory_path=memory_path),
            components=self.components(memory_path=memory_path),
            plugins=self.plugins(memory_path=memory_path),
            domain_packs=self.domain_packs(root=root, strict=strict, memory_path=memory_path),
            domain_context=self.domain_context(root=root, strict=strict, memory_path=memory_path),
            endpoints=self.catalog(),
            studio=self.studio(memory_path=memory_path),
        )

    def studio_ux_structure(
        self,
        *,
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        return build_studio_ux_structure(
            runtime_binding=self.studio_binding(root=root, strict=strict, memory_path=memory_path)
        )

    def studio_visual_design(self) -> Dict[str, Any]:
        return build_studio_visual_design_system()

    def studio_binding_run(
        self,
        *,
        message: str,
        conversation_id: str = "studio",
        root: str | Path | None = None,
        strict: bool = False,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        execution = self.studio_run(
            message=message,
            conversation_id=conversation_id,
            memory_path=memory_path,
        )
        refreshed = self.studio_binding(root=root, strict=strict, memory_path=memory_path)
        return build_studio_runtime_run_binding(execution=execution, refreshed_binding=refreshed)

    def studio_run(
        self,
        *,
        message: str,
        conversation_id: str = "studio",
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        client = StudioAPIClient(requester=self._local_requester)
        return client.run_message(
            message=message,
            conversation_id=conversation_id,
            memory_path=str(memory_path) if memory_path else None,
        )

    def studio_replay(self, *, path: str | Path, memory_path: str | Path | None = None) -> Dict[str, Any]:
        client = StudioAPIClient(requester=self._local_requester)
        return client.replay_session(path=str(path), memory_path=str(memory_path) if memory_path else None)

    def human_demo_scenario(self) -> Dict[str, Any]:
        return HumanTestDemoRunner(requester=self._local_requester).scenario_contract()

    def domain_flow_scenario(self) -> Dict[str, Any]:
        return DemoDomainRuntimeFlowRunner(api=self).scenario_contract()

    def run_domain_flow(
        self,
        *,
        message: str,
        conversation_id: str = "demo-domain-flow",
        root: str | Path = "examples/domain_packs",
        pack_name: str | None = None,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        return DemoDomainRuntimeFlowRunner(api=self).run(
            message=message,
            conversation_id=conversation_id,
            root=root,
            pack_name=pack_name,
            memory_path=memory_path,
        )

    def deploy_package(
        self,
        *,
        app_name: str = "aca-framework",
        host: str = "0.0.0.0",
        port_env: str = "PORT",
        fallback_port: int = 8765,
        studio_path: str | Path = "studio/index.html",
        domain_pack_root: str | Path = "examples/domain_packs",
    ) -> Dict[str, Any]:
        return build_deployable_web_package(
            app_name=app_name,
            host=host,
            port_env=port_env,
            fallback_port=fallback_port,
            studio_path=studio_path,
            domain_pack_root=domain_pack_root,
        )

    def validate_deploy_package(
        self,
        *,
        project_root: str | Path = ".",
        package: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return validate_deployable_web_package(project_root=project_root, package=package)


    def public_demo_manifest(
        self,
        *,
        demo_name: str = "aca-public-web-demo",
        public_base_url: str = "https://example.com",
        domain_pack_root: str | Path = "examples/domain_packs",
        default_domain_pack: str = "customer_support",
        studio_path: str | Path = "studio/index.html",
        port_env: str = "PORT",
        fallback_port: int = 8765,
    ) -> Dict[str, Any]:
        return build_public_web_demo_manifest(
            demo_name=demo_name,
            public_base_url=public_base_url,
            domain_pack_root=domain_pack_root,
            default_domain_pack=default_domain_pack,
            studio_path=studio_path,
            port_env=port_env,
            fallback_port=fallback_port,
        )

    def public_demo_readiness(
        self,
        *,
        project_root: str | Path = ".",
        manifest: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return validate_public_web_demo_readiness(project_root=project_root, manifest=manifest)


    def public_demo_runtime_adapter(
        self,
        *,
        public_base_url: str = "https://example.com",
        host: str = "0.0.0.0",
        port_env: str = "PORT",
        fallback_port: int = 8765,
        domain_pack_root: str | Path = "examples/domain_packs",
        default_domain_pack: str = "customer_support",
        studio_path: str | Path = "studio/index.html",
        demo_name: str = "aca-public-web-demo",
    ) -> Dict[str, Any]:
        return build_public_demo_runtime_adapter(
            public_base_url=public_base_url,
            host=host,
            port_env=port_env,
            fallback_port=fallback_port,
            domain_pack_root=domain_pack_root,
            default_domain_pack=default_domain_pack,
            studio_path=studio_path,
            demo_name=demo_name,
        )

    def validate_public_demo_runtime_adapter(
        self,
        *,
        project_root: str | Path = ".",
        adapter: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        return validate_public_demo_runtime_adapter(project_root=project_root, adapter=adapter)

    def public_demo_polish(self) -> Dict[str, Any]:
        return build_public_demo_polish()

    def validate_public_demo_polish(self, *, polish: Mapping[str, Any] | None = None) -> Dict[str, Any]:
        return validate_public_demo_polish(polish=polish)

    def run_human_demo(
        self,
        *,
        conversation_id: str = "human-demo",
        memory_path: str | Path | None = None,
        format: str = "dict",
    ) -> Dict[str, Any] | str:
        runner = HumanTestDemoRunner(requester=self._local_requester)
        if format == "markdown":
            return runner.run_markdown(
                conversation_id=conversation_id,
                memory_path=str(memory_path) if memory_path else None,
            )
        if format != "dict":
            raise ValueError(f"Unsupported human demo format: {format}.")
        return runner.run(
            conversation_id=conversation_id,
            memory_path=str(memory_path) if memory_path else None,
        )

    def _local_requester(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | str | None = None,
        body: Mapping[str, Any] | bytes | str | None = None,
    ) -> Dict[str, Any]:
        method = method.upper()
        params = dict(query or {}) if isinstance(query, Mapping) else {}
        payload = dict(body or {}) if isinstance(body, Mapping) else {}
        memory_path = payload.get("memory_path") or params.get("memory_path")

        if method == "GET" and path == "/health":
            return self.health(memory_path=memory_path)
        if method == "GET" and path == "/runtime/status":
            return self.status(memory_path=memory_path)
        if method == "GET" and path == "/studio/state":
            return self.studio_state(memory_path=memory_path)
        if method == "GET" and path == "/studio/binding":
            return self.studio_binding(root=params.get("root"), strict=bool(params.get("strict")), memory_path=memory_path)
        if method == "GET" and path == "/studio/ux":
            return self.studio_ux_structure(root=params.get("root"), strict=bool(params.get("strict")), memory_path=memory_path)
        if method == "GET" and path == "/studio/design":
            return self.studio_visual_design()
        if method == "GET" and path == "/runtime/studio":
            return self.studio(memory_path=memory_path)
        if method == "GET" and path == "/runtime/metrics":
            return self.metrics(memory_path=memory_path)
        if method == "GET" and path == "/runtime/components":
            return self.components(memory_path=memory_path)
        if method == "GET" and path == "/runtime/plugins":
            return self.plugins(memory_path=memory_path)
        if method == "GET" and path == "/runtime/domain-packs":
            return self.domain_packs(root=params.get("root"), strict=bool(params.get("strict")), memory_path=memory_path)
        if method == "GET" and path == "/runtime/domain-context":
            return self.domain_context(root=params.get("root"), strict=bool(params.get("strict")), memory_path=memory_path)
        if method == "GET" and path == "/public-demo/polish":
            return self.public_demo_polish()
        if method == "GET" and path == "/public-demo/polish/validate":
            return self.validate_public_demo_polish()
        if method == "POST" and path == "/studio/binding/run":
            return self.studio_binding_run(
                message=payload.get("message"),
                conversation_id=payload.get("conversation_id") or "studio",
                root=payload.get("root") or params.get("root"),
                strict=bool(payload.get("strict") or params.get("strict")),
                memory_path=memory_path,
            )
        if method == "POST" and path == "/runtime/events":
            return self.process_event(
                event_type=payload.get("event_type") or payload.get("type"),
                payload=payload.get("payload"),
                metadata=payload.get("metadata"),
                memory_path=memory_path,
                include_trace=bool(payload.get("include_trace")),
                include_introspection=bool(payload.get("include_introspection")),
                include_studio=bool(payload.get("include_studio")),
            )
        if method == "POST" and path == "/sessions/replay":
            return self.replay_session(path=payload.get("path"), memory_path=memory_path)

        if method == "GET" and path == "/public-demo/manifest":
            return self.public_demo_manifest(
                public_base_url=params.get("public_base_url") or "https://example.com",
                demo_name=params.get("demo_name") or "aca-public-web-demo",
            )
        if method == "GET" and path == "/public-demo/readiness":
            return self.public_demo_readiness(project_root=params.get("project_root") or ".")
        if method == "GET" and path == "/public-demo/runtime-adapter":
            return self.public_demo_runtime_adapter(
                public_base_url=params.get("public_base_url") or "https://example.com",
                host=params.get("host") or "0.0.0.0",
                port_env=params.get("port_env") or "PORT",
                fallback_port=int(params.get("fallback_port") or 8765),
                domain_pack_root=params.get("domain_pack_root") or "examples/domain_packs",
                default_domain_pack=params.get("default_domain_pack") or "customer_support",
                studio_path=params.get("studio_path") or "studio/index.html",
                demo_name=params.get("demo_name") or "aca-public-web-demo",
            )
        if method == "GET" and path == "/public-demo/runtime-adapter/validate":
            return self.validate_public_demo_runtime_adapter(project_root=params.get("project_root") or ".")
        if method == "GET" and path == "/demo/human-test":
            return self.human_demo_scenario()
        if method == "POST" and path == "/demo/human-test":
            return self.run_human_demo(
                conversation_id=payload.get("conversation_id") or "human-demo",
                memory_path=payload.get("memory_path") or memory_path,
                format=payload.get("format") or "dict",
            )
        if method == "GET" and path == "/demo/domain-flow":
            return self.domain_flow_scenario()
        if method == "POST" and path == "/demo/domain-flow":
            return self.run_domain_flow(
                message=payload.get("message"),
                conversation_id=payload.get("conversation_id") or "demo-domain-flow",
                root=payload.get("root") or params.get("root") or "examples/domain_packs",
                pack_name=payload.get("pack_name") or params.get("pack_name"),
                memory_path=payload.get("memory_path") or memory_path,
            )
        if method == "GET" and path == "/deploy/package":
            return self.deploy_package(
                app_name=params.get("app_name") or "aca-framework",
                host=params.get("host") or "0.0.0.0",
                port_env=params.get("port_env") or "PORT",
                fallback_port=int(params.get("fallback_port") or 8765),
                studio_path=params.get("studio_path") or "studio/index.html",
                domain_pack_root=params.get("domain_pack_root") or "examples/domain_packs",
            )
        if method == "GET" and path == "/deploy/validate":
            return self.validate_deploy_package(project_root=params.get("project_root") or ".")
        raise ValueError(f"Unsupported local Studio API request: {method} {path}.")

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
