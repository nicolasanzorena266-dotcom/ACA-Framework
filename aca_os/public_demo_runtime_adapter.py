from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping

from aca_os.public_web_demo import build_public_web_demo_manifest, validate_public_web_demo_readiness


DEFAULT_PUBLIC_DEMO_ADAPTER_CONTRACT = "public_demo_runtime_adapter.v1"
DEFAULT_PUBLIC_BASE_URL = "https://example.com"
DEFAULT_PUBLIC_HOST = "0.0.0.0"
DEFAULT_PORT_ENV = "PORT"
DEFAULT_FALLBACK_PORT = 8765
DEFAULT_DOMAIN_PACK_ROOT = Path("examples/domain_packs")
DEFAULT_DOMAIN_PACK = "customer_support"
DEFAULT_STUDIO_PATH = Path("studio/index.html")


@dataclass(frozen=True)
class PublicDemoRuntimeAdapterConfig:
    """Runtime-facing adapter contract for a public ACA demo.

    The adapter is a deployment/interface description only. It does not embed
    domain behavior, mutate Runtime Core, or depend on external AI services.
    HTTP servers and cloud platforms can consume this contract to expose the
    existing Runtime REST boundary safely.
    """

    public_base_url: str = DEFAULT_PUBLIC_BASE_URL
    host: str = DEFAULT_PUBLIC_HOST
    port_env: str = DEFAULT_PORT_ENV
    fallback_port: int = DEFAULT_FALLBACK_PORT
    domain_pack_root: Path = DEFAULT_DOMAIN_PACK_ROOT
    default_domain_pack: str = DEFAULT_DOMAIN_PACK
    studio_path: Path = DEFAULT_STUDIO_PATH
    demo_name: str = "aca-public-web-demo"
    extra_env: Mapping[str, str] = field(default_factory=dict)

    @property
    def normalized_base_url(self) -> str:
        return self.public_base_url.rstrip("/")

    @property
    def startup_command(self) -> str:
        return f"python tools/aca_web.py --host {self.host}"

    @property
    def public_routes(self) -> Dict[str, str]:
        base = self.normalized_base_url
        return {
            "studio": f"{base}/studio",
            "health": f"{base}/health",
            "runtime_status": f"{base}/runtime/status",
            "studio_binding": f"{base}/studio/binding",
            "domain_flow": f"{base}/demo/domain-flow",
            "public_demo_manifest": f"{base}/public-demo/manifest",
            "public_demo_readiness": f"{base}/public-demo/readiness",
            "runtime_adapter": f"{base}/public-demo/runtime-adapter",
        }

    @property
    def environment(self) -> Dict[str, str]:
        env = {
            self.port_env: str(self.fallback_port),
            "ACA_HOST": self.host,
            "ACA_PORT": str(self.fallback_port),
            "ACA_PUBLIC_BASE_URL": self.normalized_base_url,
            "ACA_DOMAIN_PACK_ROOT": str(self.domain_pack_root),
            "ACA_DEFAULT_DOMAIN_PACK": self.default_domain_pack,
            "ACA_STUDIO_PATH": str(self.studio_path),
        }
        env.update(dict(self.extra_env))
        return env

    def to_dict(self) -> Dict[str, Any]:
        manifest = build_public_web_demo_manifest(
            demo_name=self.demo_name,
            public_base_url=self.normalized_base_url,
            domain_pack_root=self.domain_pack_root,
            default_domain_pack=self.default_domain_pack,
            studio_path=self.studio_path,
            port_env=self.port_env,
            fallback_port=self.fallback_port,
            extra_env=self.extra_env,
        )
        return {
            "contract": DEFAULT_PUBLIC_DEMO_ADAPTER_CONTRACT,
            "demo_name": self.demo_name,
            "mode": "public-web-demo",
            "runtime": {
                "type": "aca-deterministic-runtime",
                "offline_capable": True,
                "external_ai_required": False,
                "business_logic_location": "runtime",
                "interface_logic_location": "adapter",
            },
            "binding": {
                "host": self.host,
                "port_env": self.port_env,
                "fallback_port": self.fallback_port,
                "startup_command": self.startup_command,
                "healthcheck_path": "/health",
            },
            "public_base_url": self.normalized_base_url,
            "public_routes": self.public_routes,
            "default_domain": {
                "pack_name": self.default_domain_pack,
                "root": str(self.domain_pack_root),
                "demo_endpoint": "/demo/domain-flow",
                "demo_body": {
                    "message": "Necesito ayuda con un reclamo",
                    "pack_name": self.default_domain_pack,
                    "root": str(self.domain_pack_root),
                },
            },
            "studio": {
                "path": str(self.studio_path),
                "route": "/studio",
                "binding_endpoint": "/studio/binding",
                "run_endpoint": "/studio/binding/run",
            },
            "environment": self.environment,
            "smoke_checks": [
                {"method": "GET", "path": "/health", "expect": {"status_code": 200, "status": "ok"}},
                {"method": "GET", "path": "/public-demo/runtime-adapter", "expect": {"status_code": 200}},
                {"method": "GET", "path": "/studio/binding", "expect": {"status_code": 200}},
                {"method": "POST", "path": "/demo/domain-flow", "body": {"message": "Necesito ayuda con un reclamo", "pack_name": self.default_domain_pack, "root": str(self.domain_pack_root)}, "expect": {"status_code": 200}},
            ],
            "public_demo_manifest": manifest,
            "non_goals": [
                "no visual redesign",
                "no external LLM dependency",
                "no business logic in web adapter",
                "no platform-specific lock-in",
            ],
        }


@dataclass(frozen=True)
class PublicDemoRuntimeAdapterValidation:
    valid: bool
    adapter: Dict[str, Any]
    readiness: Dict[str, Any]
    errors: list[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "adapter": self.adapter,
            "readiness": self.readiness,
            "errors": list(self.errors),
        }


def build_public_demo_runtime_adapter(
    *,
    public_base_url: str = DEFAULT_PUBLIC_BASE_URL,
    host: str = DEFAULT_PUBLIC_HOST,
    port_env: str = DEFAULT_PORT_ENV,
    fallback_port: int = DEFAULT_FALLBACK_PORT,
    domain_pack_root: str | Path = DEFAULT_DOMAIN_PACK_ROOT,
    default_domain_pack: str = DEFAULT_DOMAIN_PACK,
    studio_path: str | Path = DEFAULT_STUDIO_PATH,
    demo_name: str = "aca-public-web-demo",
    extra_env: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    if not public_base_url:
        raise ValueError("public_base_url is required.")
    if not host:
        raise ValueError("host is required.")
    if not port_env:
        raise ValueError("port_env is required.")
    if int(fallback_port) <= 0 or int(fallback_port) > 65535:
        raise ValueError("fallback_port must be between 1 and 65535.")
    if not default_domain_pack:
        raise ValueError("default_domain_pack is required.")

    return PublicDemoRuntimeAdapterConfig(
        public_base_url=public_base_url,
        host=host,
        port_env=port_env,
        fallback_port=int(fallback_port),
        domain_pack_root=Path(domain_pack_root),
        default_domain_pack=default_domain_pack,
        studio_path=Path(studio_path),
        demo_name=demo_name,
        extra_env=dict(extra_env or {}),
    ).to_dict()


def build_public_demo_runtime_adapter_from_env(env: Mapping[str, str] | None = None) -> Dict[str, Any]:
    source = dict(os.environ if env is None else env)
    port_env = source.get("ACA_PORT_ENV") or DEFAULT_PORT_ENV
    fallback_port = int(source.get(port_env) or source.get("ACA_PORT") or DEFAULT_FALLBACK_PORT)
    return build_public_demo_runtime_adapter(
        public_base_url=source.get("ACA_PUBLIC_BASE_URL") or DEFAULT_PUBLIC_BASE_URL,
        host=source.get("ACA_HOST") or DEFAULT_PUBLIC_HOST,
        port_env=port_env,
        fallback_port=fallback_port,
        domain_pack_root=source.get("ACA_DOMAIN_PACK_ROOT") or str(DEFAULT_DOMAIN_PACK_ROOT),
        default_domain_pack=source.get("ACA_DEFAULT_DOMAIN_PACK") or DEFAULT_DOMAIN_PACK,
        studio_path=source.get("ACA_STUDIO_PATH") or str(DEFAULT_STUDIO_PATH),
        demo_name=source.get("ACA_PUBLIC_DEMO_NAME") or "aca-public-web-demo",
    )


def validate_public_demo_runtime_adapter(
    *,
    project_root: str | Path = ".",
    adapter: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = dict(adapter or build_public_demo_runtime_adapter())
    errors: list[str] = []

    if payload.get("contract") != DEFAULT_PUBLIC_DEMO_ADAPTER_CONTRACT:
        errors.append("invalid adapter contract")
    if payload.get("runtime", {}).get("business_logic_location") != "runtime":
        errors.append("runtime business logic must stay in runtime")
    if payload.get("runtime", {}).get("external_ai_required") is not False:
        errors.append("public demo adapter must not require external AI")
    if payload.get("binding", {}).get("host") != "0.0.0.0":
        errors.append("public demo adapter must bind to 0.0.0.0")
    if "/demo/domain-flow" != payload.get("default_domain", {}).get("demo_endpoint"):
        errors.append("default demo endpoint must be /demo/domain-flow")

    readiness = validate_public_web_demo_readiness(
        project_root=project_root,
        manifest=payload.get("public_demo_manifest"),
    )
    if not readiness.get("ready"):
        errors.append("public demo readiness failed")

    return PublicDemoRuntimeAdapterValidation(
        valid=not errors,
        adapter=payload,
        readiness=readiness,
        errors=errors,
    ).to_dict()
