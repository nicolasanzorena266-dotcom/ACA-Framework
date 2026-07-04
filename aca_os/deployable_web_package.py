from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping

from aca_os.web_runtime_launcher import DEFAULT_PORT, build_local_web_runtime_plan


DEFAULT_DEPLOY_HOST = "0.0.0.0"
DEFAULT_PORT_ENV = "PORT"
DEFAULT_DEPLOY_STUDIO_PATH = Path("studio/index.html")


@dataclass(frozen=True)
class DeployableWebPackageConfig:
    """Deployment-facing ACA Web Runtime package contract.

    This module describes deploy requirements only. It does not start servers,
    execute Runtime behavior or embed business/domain logic. External platforms
    can read the contract to know how ACA should be launched and checked.
    """

    app_name: str = "aca-framework"
    host: str = DEFAULT_DEPLOY_HOST
    port_env: str = DEFAULT_PORT_ENV
    fallback_port: int = DEFAULT_PORT
    studio_path: Path = DEFAULT_DEPLOY_STUDIO_PATH
    domain_pack_root: Path = Path("examples/domain_packs")
    python_version: str = ">=3.10"
    extra_env: Mapping[str, str] = field(default_factory=dict)

    @property
    def startup_command(self) -> str:
        return f"python tools/aca_web.py --host {self.host}"

    @property
    def local_startup_command(self) -> str:
        return f"python tools/aca_web.py --host 127.0.0.1 --port {self.fallback_port} --open"

    @property
    def healthcheck_path(self) -> str:
        return "/health"

    @property
    def studio_path_route(self) -> str:
        return "/studio"

    @property
    def required_files(self) -> List[str]:
        return [
            "tools/aca_web.py",
            "aca_os/runtime_rest.py",
            "aca_os/runtime_api_endpoints.py",
            str(self.studio_path),
            str(self.domain_pack_root),
            "pyproject.toml",
        ]

    def to_dict(self) -> Dict[str, Any]:
        env = {
            "ACA_HOST": self.host,
            "ACA_PORT": str(self.fallback_port),
            self.port_env: str(self.fallback_port),
            "ACA_DOMAIN_PACK_ROOT": str(self.domain_pack_root),
        }
        env.update(dict(self.extra_env))
        return {
            "contract": "deployable_web_package.v1",
            "app_name": self.app_name,
            "runtime": "python",
            "python_version": self.python_version,
            "process": {
                "type": "web",
                "command": self.startup_command,
                "local_command": self.local_startup_command,
                "host": self.host,
                "port_env": self.port_env,
                "fallback_port": self.fallback_port,
            },
            "healthcheck": {
                "method": "GET",
                "path": self.healthcheck_path,
                "expected_status": 200,
                "expected_json_status": "ok",
            },
            "routes": {
                "studio": self.studio_path_route,
                "health": self.healthcheck_path,
                "runtime_status": "/runtime/status",
                "studio_binding": "/studio/binding",
                "demo_domain_flow": "/demo/domain-flow",
            },
            "assets": {
                "studio_html": str(self.studio_path),
                "domain_pack_root": str(self.domain_pack_root),
            },
            "environment": env,
            "required_files": self.required_files,
            "non_goals": [
                "no LLM dependency",
                "no external AI service requirement",
                "no business logic in deployment wrapper",
            ],
        }


@dataclass(frozen=True)
class DeployableWebPackageValidation:
    valid: bool
    missing_files: List[str]
    package: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "missing_files": list(self.missing_files),
            "package": self.package,
        }


def build_deployable_web_package(
    *,
    app_name: str = "aca-framework",
    host: str = DEFAULT_DEPLOY_HOST,
    port_env: str = DEFAULT_PORT_ENV,
    fallback_port: int = DEFAULT_PORT,
    studio_path: str | Path = DEFAULT_DEPLOY_STUDIO_PATH,
    domain_pack_root: str | Path = "examples/domain_packs",
    extra_env: Mapping[str, str] | None = None,
) -> Dict[str, Any]:
    if not app_name:
        raise ValueError("app_name is required.")
    if not host:
        raise ValueError("host is required.")
    if not port_env:
        raise ValueError("port_env is required.")
    if int(fallback_port) <= 0 or int(fallback_port) > 65535:
        raise ValueError("fallback_port must be between 1 and 65535.")

    config = DeployableWebPackageConfig(
        app_name=app_name,
        host=host,
        port_env=port_env,
        fallback_port=int(fallback_port),
        studio_path=Path(studio_path),
        domain_pack_root=Path(domain_pack_root),
        extra_env=dict(extra_env or {}),
    )
    package = config.to_dict()
    package["local_runtime_plan"] = build_local_web_runtime_plan(
        host="127.0.0.1",
        port=int(fallback_port),
        studio_path=studio_path,
        open_browser=True,
    ).to_dict()
    return package


def validate_deployable_web_package(
    *,
    project_root: str | Path = ".",
    package: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = dict(package or build_deployable_web_package())
    root = Path(project_root)
    required_files = list(payload.get("required_files", []))
    missing = [path for path in required_files if not (root / path).exists()]
    return DeployableWebPackageValidation(
        valid=not missing,
        missing_files=missing,
        package=payload,
    ).to_dict()
