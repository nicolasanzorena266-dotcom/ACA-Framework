from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from aca_os.execution_trace import sanitize
from aca_os.hosting_target_contract import build_hosting_target_contract, validate_hosting_target_contract
from aca_os.hosted_studio_assets import build_hosted_studio_assets, validate_hosted_studio_assets
from aca_os.public_web_demo import build_public_web_demo_manifest, validate_public_web_demo_readiness

HOSTED_RUNTIME_HEALTHCHECK = "hosted_runtime_healthcheck.v1"


@dataclass(frozen=True)
class HostedHealthCheckItem:
    """One platform-facing hosted runtime health check item."""

    id: str
    status: str
    message: str
    required: bool = True
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "id": self.id,
                "status": self.status,
                "message": self.message,
                "required": self.required,
                "details": dict(self.details),
            }
        )


@dataclass(frozen=True)
class HostedRuntimeHealthcheck:
    """Transport-neutral healthcheck for hosted ACA Studio demos.

    This is not a socket server and not a deployment script. It composes the
    existing runtime/hosting contracts into a host-friendly response that can be
    exposed by REST adapters and consumed by platforms or smoke tests.
    """

    mode: str = "hosted"
    project_root: Path = Path(".")
    public_base_url: str = "https://aca-demo.example.com"
    port_env: str = "PORT"
    fallback_port: int = 8765
    default_domain_pack: str = "customer_support"
    domain_pack_root: Path = Path("examples/domain_packs")
    studio_path: Path = Path("studio/index.html")
    expected_routes: tuple[str, ...] = (
        "/health",
        "/studio",
        "/runtime/status",
        "/studio/binding",
        "/demo/domain-flow",
        "/hosting/target",
        "/hosting/healthcheck",
        "/hosting/studio-assets",
        "/deploy/smoke-tests",
        "/deploy/smoke-tests/run",
        "/deploy/smoke-tests/validate",
    )

    def to_dict(self) -> Dict[str, Any]:
        checks = self._checks()
        blocking = [check for check in checks if check.required and check.status != "ok"]
        status = "ok" if not blocking else "degraded"
        return sanitize(
            {
                "contract": HOSTED_RUNTIME_HEALTHCHECK,
                "status": status,
                "mode": self.mode,
                "summary": {
                    "ok": sum(1 for check in checks if check.status == "ok"),
                    "degraded": sum(1 for check in checks if check.status == "degraded"),
                    "failed": sum(1 for check in checks if check.status == "failed"),
                    "required_failures": len(blocking),
                },
                "runtime": {
                    "external_ai_required": False,
                    "offline_core_supported": True,
                    "business_logic_location": "runtime",
                    "interface_logic_location": "hosted_adapter",
                },
                "hosting": {
                    "public_base_url": self.public_base_url.rstrip("/"),
                    "port_env": self.port_env,
                    "fallback_port": self.fallback_port,
                    "healthcheck_path": "/hosting/healthcheck",
                    "platform_healthcheck_path": "/health",
                    "startup_command": "python tools/aca_web.py --host 0.0.0.0",
                },
                "assets": {
                    "studio_html": str(self.studio_path),
                    "domain_pack_root": str(self.domain_pack_root),
                    "default_domain_pack": self.default_domain_pack,
                },
                "checks": [check.to_dict() for check in checks],
                "acceptance_criteria": [
                    "hosted healthcheck returns status ok",
                    "platform /health route remains available",
                    "Studio asset is present",
                    "hosted Studio asset strategy validates",
                    "deployment smoke tests are available",
                    "default Domain Pack is present",
                    "hosting target contract validates",
                    "public demo readiness validates",
                    "runtime behavior remains outside hosted adapter",
                ],
                "metadata": {"sprint": 61, "epic": "Hosted Demo Path"},
            }
        )

    def _checks(self) -> list[HostedHealthCheckItem]:
        root = self.project_root
        hosting_contract = build_hosting_target_contract(
            public_base_url=self.public_base_url,
            port_env=self.port_env,
            fallback_port=self.fallback_port,
        )
        hosting_validation = validate_hosting_target_contract(project_root=root, contract=hosting_contract)
        public_manifest = build_public_web_demo_manifest(
            public_base_url=self.public_base_url,
            domain_pack_root=self.domain_pack_root,
            default_domain_pack=self.default_domain_pack,
            studio_path=self.studio_path,
            port_env=self.port_env,
            fallback_port=self.fallback_port,
        )
        public_readiness = validate_public_web_demo_readiness(project_root=root, manifest=public_manifest)
        studio_asset_strategy = build_hosted_studio_assets(
            project_root=root,
            public_base_url=self.public_base_url,
            studio_path=self.studio_path,
        )
        studio_asset_validation = validate_hosted_studio_assets(project_root=root, strategy=studio_asset_strategy)
        route_paths = _route_paths(hosting_contract.get("routes", []))
        missing_routes = sorted(set(self.expected_routes) - route_paths)
        studio_exists = (root / self.studio_path).exists()
        domain_root_exists = (root / self.domain_pack_root).exists()
        domain_pack_exists = (root / self.domain_pack_root / self.default_domain_pack).exists()
        port_value = os.environ.get(self.port_env) or os.environ.get("ACA_PORT") or str(self.fallback_port)

        return [
            HostedHealthCheckItem(
                "runtime_contract",
                "ok",
                "Hosted runtime contract is deterministic and does not require external AI.",
                details={"external_ai_required": False, "business_logic_location": "runtime"},
            ),
            HostedHealthCheckItem(
                "hosting_target_contract",
                "ok" if hosting_validation.get("valid") else "failed",
                "Hosting target contract validates." if hosting_validation.get("valid") else "Hosting target contract has validation errors.",
                details={"errors": hosting_validation.get("errors", [])},
            ),
            HostedHealthCheckItem(
                "public_demo_readiness",
                "ok" if public_readiness.get("ready") else "failed",
                "Public demo readiness validates." if public_readiness.get("ready") else "Public demo readiness is incomplete.",
                details={"missing_files": public_readiness.get("missing_files", [])},
            ),
            HostedHealthCheckItem(
                "studio_asset",
                "ok" if studio_exists else "failed",
                "ACA Studio asset is present." if studio_exists else "ACA Studio asset is missing.",
                details={"path": str(self.studio_path)},
            ),
            HostedHealthCheckItem(
                "hosted_studio_assets",
                "ok" if studio_asset_validation.get("valid") else "failed",
                "Hosted Studio asset strategy validates." if studio_asset_validation.get("valid") else "Hosted Studio asset strategy has validation errors.",
                details={"errors": studio_asset_validation.get("errors", [])},
            ),
            HostedHealthCheckItem(
                "domain_pack_root",
                "ok" if domain_root_exists else "failed",
                "Domain Pack root is present." if domain_root_exists else "Domain Pack root is missing.",
                details={"path": str(self.domain_pack_root)},
            ),
            HostedHealthCheckItem(
                "default_domain_pack",
                "ok" if domain_pack_exists else "failed",
                "Default Domain Pack is present." if domain_pack_exists else "Default Domain Pack is missing.",
                details={"pack": self.default_domain_pack, "root": str(self.domain_pack_root)},
            ),
            HostedHealthCheckItem(
                "route_contract",
                "ok" if not missing_routes else "failed",
                "Hosted routes are declared." if not missing_routes else "Hosted route contract is missing required routes.",
                details={"missing_routes": missing_routes, "declared_routes": sorted(route_paths)},
            ),
            HostedHealthCheckItem(
                "deployment_smoke_tests",
                "ok" if (root / "aca_os" / "deployment_smoke_tests.py").exists() else "failed",
                "Deployment smoke test module is present." if (root / "aca_os" / "deployment_smoke_tests.py").exists() else "Deployment smoke test module is missing.",
                details={"path": "aca_os/deployment_smoke_tests.py"},
            ),
            HostedHealthCheckItem(
                "port_configuration",
                "ok" if _valid_port(port_value) else "failed",
                "Hosted port configuration is valid." if _valid_port(port_value) else "Hosted port configuration is invalid.",
                details={"port_env": self.port_env, "value": port_value, "fallback_port": self.fallback_port},
            ),
        ]


def build_hosted_runtime_healthcheck(
    *,
    mode: str = "hosted",
    project_root: str | Path = ".",
    public_base_url: str = "https://aca-demo.example.com",
    port_env: str = "PORT",
    fallback_port: int = 8765,
    default_domain_pack: str = "customer_support",
    domain_pack_root: str | Path = "examples/domain_packs",
    studio_path: str | Path = "studio/index.html",
) -> Dict[str, Any]:
    if mode not in {"hosted", "local"}:
        raise ValueError("mode must be hosted or local.")
    if not public_base_url:
        raise ValueError("public_base_url is required.")
    if not port_env:
        raise ValueError("port_env is required.")
    if int(fallback_port) <= 0 or int(fallback_port) > 65535:
        raise ValueError("fallback_port must be between 1 and 65535.")
    if not default_domain_pack:
        raise ValueError("default_domain_pack is required.")

    return HostedRuntimeHealthcheck(
        mode=mode,
        project_root=Path(project_root),
        public_base_url=public_base_url,
        port_env=port_env,
        fallback_port=int(fallback_port),
        default_domain_pack=default_domain_pack,
        domain_pack_root=Path(domain_pack_root),
        studio_path=Path(studio_path),
    ).to_dict()


def validate_hosted_runtime_healthcheck(
    *,
    healthcheck: Mapping[str, Any] | None = None,
    project_root: str | Path = ".",
) -> Dict[str, Any]:
    payload = dict(healthcheck or build_hosted_runtime_healthcheck(project_root=project_root))
    errors: list[str] = []

    if payload.get("contract") != HOSTED_RUNTIME_HEALTHCHECK:
        errors.append("invalid hosted runtime healthcheck contract")
    if payload.get("runtime", {}).get("external_ai_required") is not False:
        errors.append("hosted healthcheck must not require external AI")
    if payload.get("runtime", {}).get("business_logic_location") != "runtime":
        errors.append("hosted adapter must keep business logic in runtime")
    if payload.get("hosting", {}).get("platform_healthcheck_path") != "/health":
        errors.append("platform healthcheck path must remain /health")
    if payload.get("hosting", {}).get("healthcheck_path") != "/hosting/healthcheck":
        errors.append("hosted healthcheck path must be /hosting/healthcheck")

    checks = payload.get("checks") or []
    for check in checks:
        if isinstance(check, Mapping) and check.get("required") is not False and check.get("status") != "ok":
            errors.append(f"required check failed: {check.get('id')}")

    return sanitize(
        {
            "valid": not errors,
            "errors": errors,
            "healthcheck": payload,
            "project_root": str(project_root),
        }
    )


def _route_paths(routes: Iterable[Any]) -> set[str]:
    paths: set[str] = set()
    for route in routes:
        if isinstance(route, Mapping) and route.get("path"):
            paths.add(str(route["path"]))
    return paths


def _valid_port(value: Any) -> bool:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return False
    return 0 < port <= 65535
