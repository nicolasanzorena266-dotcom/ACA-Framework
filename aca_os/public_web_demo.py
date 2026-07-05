from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping

from aca_os.deployable_web_package import build_deployable_web_package, validate_deployable_web_package


DEFAULT_PUBLIC_DEMO_NAME = "aca-public-web-demo"
DEFAULT_PUBLIC_BASE_URL = "https://example.com"
DEFAULT_PROJECT_ROOT = Path(".")


@dataclass(frozen=True)
class PublicWebDemoConfig:
    """Public demo readiness contract for ACA Web Runtime.

    This module prepares deployment metadata only. It does not deploy anything,
    start servers or place Runtime behavior in the web layer. The public demo is
    still served by the existing Runtime REST boundary and Studio static asset.
    """

    demo_name: str = DEFAULT_PUBLIC_DEMO_NAME
    public_base_url: str = DEFAULT_PUBLIC_BASE_URL
    domain_pack_root: Path = Path("examples/domain_packs")
    default_domain_pack: str = "customer_support"
    studio_path: Path = Path("studio/index.html")
    port_env: str = "PORT"
    fallback_port: int = 8765
    extra_env: Mapping[str, str] = field(default_factory=dict)

    @property
    def normalized_base_url(self) -> str:
        return self.public_base_url.rstrip("/")

    @property
    def routes(self) -> Dict[str, str]:
        base = self.normalized_base_url
        return {
            "studio": f"{base}/studio",
            "health": f"{base}/health",
            "runtime_status": f"{base}/runtime/status",
            "studio_binding": f"{base}/studio/binding",
            "demo_domain_flow": f"{base}/demo/domain-flow",
            "deploy_package": f"{base}/deploy/package",
            "public_demo_manifest": f"{base}/public-demo/manifest",
            "public_demo_readiness": f"{base}/public-demo/readiness",
            "public_demo_runtime_adapter": f"{base}/public-demo/runtime-adapter",
        }

    @property
    def required_files(self) -> List[str]:
        return [
            "tools/aca_web.py",
            "tools/aca_deploy.py",
            "tools/aca_public_demo.py",
            "aca_os/public_web_demo.py",
            "aca_os/public_demo_runtime_adapter.py",
            "aca_os/runtime_rest.py",
            "aca_os/runtime_api_endpoints.py",
            str(self.studio_path),
            str(self.domain_pack_root),
            "deploy/aca-web-package.json",
            "deploy/public-web-demo.json",
            "pyproject.toml",
        ]

    @property
    def required_routes(self) -> List[str]:
        return [
            "/health",
            "/runtime/status",
            "/studio",
            "/studio/binding",
            "/demo/domain-flow",
            "/deploy/package",
            "/public-demo/manifest",
            "/public-demo/readiness",
            "/public-demo/runtime-adapter",
        ]

    def to_dict(self) -> Dict[str, Any]:
        env = {
            self.port_env: str(self.fallback_port),
            "ACA_HOST": "0.0.0.0",
            "ACA_PORT": str(self.fallback_port),
            "ACA_PUBLIC_BASE_URL": self.normalized_base_url,
            "ACA_DOMAIN_PACK_ROOT": str(self.domain_pack_root),
            "ACA_DEFAULT_DOMAIN_PACK": self.default_domain_pack,
        }
        env.update(dict(self.extra_env))
        return {
            "contract": "public_web_demo_prep.v1",
            "demo_name": self.demo_name,
            "public_base_url": self.normalized_base_url,
            "runtime": "python",
            "web_package": build_deployable_web_package(
                app_name=self.demo_name,
                host="0.0.0.0",
                port_env=self.port_env,
                fallback_port=self.fallback_port,
                studio_path=self.studio_path,
                domain_pack_root=self.domain_pack_root,
            ),
            "startup": {
                "command": "python tools/aca_web.py --host 0.0.0.0",
                "port_env": self.port_env,
                "healthcheck_path": "/health",
            },
            "routes": self.routes,
            "required_routes": self.required_routes,
            "assets": {
                "studio_html": str(self.studio_path),
                "domain_pack_root": str(self.domain_pack_root),
                "default_domain_pack": self.default_domain_pack,
            },
            "environment": env,
            "required_files": self.required_files,
            "smoke_checks": [
                {"method": "GET", "path": "/health", "expect": {"status_code": 200, "status": "ok"}},
                {"method": "GET", "path": "/runtime/status", "expect": {"status_code": 200}},
                {"method": "GET", "path": "/studio/binding", "expect": {"status_code": 200}},
                {
                    "method": "POST",
                    "path": "/demo/domain-flow",
                    "body": {
                        "message": "Necesito ayuda con un reclamo",
                        "pack_name": self.default_domain_pack,
                        "root": str(self.domain_pack_root),
                    },
                    "expect": {"status_code": 200},
                },
            ],
            "readiness_criteria": [
                "required files exist",
                "health endpoint returns ok",
                "Studio route is served by the web adapter",
                "demo Domain Pack flow can run without external AI services",
                "deployment command binds to 0.0.0.0 and reads the platform port env",
            ],
            "non_goals": [
                "no aesthetic redesign in this sprint",
                "no external LLM dependency",
                "no platform-specific lock-in",
            ],
        }


@dataclass(frozen=True)
class PublicWebDemoReadiness:
    ready: bool
    missing_files: List[str]
    manifest: Dict[str, Any]
    deploy_package_validation: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ready": self.ready,
            "missing_files": list(self.missing_files),
            "manifest": self.manifest,
            "deploy_package_validation": self.deploy_package_validation,
        }


def build_public_web_demo_manifest(
    *,
    demo_name: str = DEFAULT_PUBLIC_DEMO_NAME,
    public_base_url: str = DEFAULT_PUBLIC_BASE_URL,
    domain_pack_root: str | Path = "examples/domain_packs",
    default_domain_pack: str = "customer_support",
    studio_path: str | Path = "studio/index.html",
    port_env: str = "PORT",
    fallback_port: int = 8765,
    extra_env: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    if not demo_name:
        raise ValueError("demo_name is required.")
    if not public_base_url:
        raise ValueError("public_base_url is required.")
    if not default_domain_pack:
        raise ValueError("default_domain_pack is required.")
    if int(fallback_port) <= 0 or int(fallback_port) > 65535:
        raise ValueError("fallback_port must be between 1 and 65535.")

    return PublicWebDemoConfig(
        demo_name=demo_name,
        public_base_url=public_base_url,
        domain_pack_root=Path(domain_pack_root),
        default_domain_pack=default_domain_pack,
        studio_path=Path(studio_path),
        port_env=port_env,
        fallback_port=int(fallback_port),
        extra_env=dict(extra_env or {}),
    ).to_dict()


def validate_public_web_demo_readiness(
    *,
    project_root: str | Path = DEFAULT_PROJECT_ROOT,
    manifest: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = dict(manifest or build_public_web_demo_manifest())
    root = Path(project_root)
    required_files = list(payload.get("required_files", []))
    missing = [path for path in required_files if not (root / path).exists()]
    deploy_validation = validate_deployable_web_package(
        project_root=root,
        package=payload.get("web_package"),
    )
    return PublicWebDemoReadiness(
        ready=not missing and bool(deploy_validation.get("valid")),
        missing_files=missing,
        manifest=payload,
        deploy_package_validation=deploy_validation,
    ).to_dict()
