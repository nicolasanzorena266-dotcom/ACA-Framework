from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize


HOSTING_TARGET_CONTRACT = "hosting_target_contract.v1"


@dataclass(frozen=True)
class HostingRoute:
    """Public route required by a hosted ACA Studio demo."""

    id: str
    method: str
    path: str
    purpose: str
    required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "method": self.method,
            "path": self.path,
            "purpose": self.purpose,
            "required": self.required,
        }


@dataclass(frozen=True)
class HostingTargetContract:
    """Platform-neutral hosting contract for the ACA public demo path.

    The contract describes what a host must provide and what ACA exposes. It
    does not deploy, mutate runtime state, or move business logic into hosting
    scripts. Hosted surfaces remain adapters over Runtime APIs.
    """

    app_name: str = "aca-public-web-demo"
    platform: str = "generic-python-web-service"
    public_base_url: str = "https://aca-demo.example.com"
    port_env: str = "PORT"
    fallback_port: int = 8765
    routes: tuple[HostingRoute, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        routes = self.routes or default_hosting_routes()
        return sanitize(
            {
                "contract": HOSTING_TARGET_CONTRACT,
                "app": {
                    "name": self.app_name,
                    "surface": "ACA Studio",
                    "mode": "hosted-public-demo",
                    "platform": self.platform,
                    "public_base_url": self.public_base_url.rstrip("/"),
                },
                "runtime": {
                    "type": "python-web-runtime",
                    "python_version": ">=3.10",
                    "external_ai_required": False,
                    "offline_core_supported": True,
                    "business_logic_location": "runtime",
                    "interface_logic_location": "web_adapter",
                },
                "process": {
                    "type": "web",
                    "startup_command": "python tools/aca_web.py --host 0.0.0.0",
                    "local_command": "python tools/aca_web.py --host 127.0.0.1 --port 8765 --open",
                    "host": "0.0.0.0",
                    "port_env": self.port_env,
                    "fallback_port": self.fallback_port,
                    "shutdown": "SIGTERM or Ctrl+C",
                },
                "healthcheck": {
                    "method": "GET",
                    "path": "/health",
                    "expected_status_code": 200,
                    "expected_json": {"status": "ok"},
                    "timeout_seconds": 10,
                },
                "routes": [route.to_dict() for route in routes],
                "public_routes": {
                    route.id: f"{self.public_base_url.rstrip('/')}{route.path}" for route in routes
                },
                "assets": {
                    "studio_html": "studio/index.html",
                    "domain_pack_root": "examples/domain_packs",
                    "default_domain_pack": "customer_support",
                    "deploy_config": "deploy/public-web-demo.json",
                    "hosting_contract": "deploy/hosting-target-contract.json",
                },
                "environment": {
                    self.port_env: str(self.fallback_port),
                    "ACA_HOST": "0.0.0.0",
                    "ACA_PORT": str(self.fallback_port),
                    "ACA_PUBLIC_BASE_URL": self.public_base_url.rstrip("/"),
                    "ACA_DOMAIN_PACK_ROOT": "examples/domain_packs",
                    "ACA_DEFAULT_DOMAIN_PACK": "customer_support",
                    "ACA_STUDIO_PATH": "studio/index.html",
                },
                "required_files": [
                    "tools/aca_web.py",
                    "tools/aca_public_demo.py",
                    "aca_os/runtime_rest.py",
                    "aca_os/runtime_api_endpoints.py",
                    "aca_os/public_demo_runtime_adapter.py",
                    "aca_os/public_demo_polish.py",
                    "studio/index.html",
                    "examples/domain_packs",
                    "deploy/public-web-demo.json",
                    "deploy/hosting-target-contract.json",
                    "aca_os/hosted_runtime_healthcheck.py",
                    "aca_os/hosted_studio_assets.py",
                    "aca_os/deployment_smoke_tests.py",
                    "pyproject.toml",
                ],
                "platform_requirements": [
                    "must run a Python 3.10+ web process",
                    "must provide an HTTP port through the configured port environment variable",
                    "must route public HTTP traffic to the ACA web process",
                    "must call GET /health for service health",
                    "must preserve project files required by the runtime and Studio shell",
                ],
                "compatible_targets": [
                    {
                        "id": "render-web-service",
                        "label": "Render Web Service",
                        "start_command": "python tools/aca_web.py --host 0.0.0.0",
                        "port_strategy": "PORT environment variable",
                    },
                    {
                        "id": "railway-service",
                        "label": "Railway Service",
                        "start_command": "python tools/aca_web.py --host 0.0.0.0",
                        "port_strategy": "PORT environment variable",
                    },
                    {
                        "id": "generic-python-host",
                        "label": "Generic Python HTTP Host",
                        "start_command": "python tools/aca_web.py --host 0.0.0.0",
                        "port_strategy": "PORT with 8765 fallback",
                    },
                ],
                "acceptance_criteria": [
                    "GET /health returns status ok",
                    "GET /studio serves ACA Studio",
                    "GET /hosting/target returns hosting_target_contract.v1",
                    "GET /hosting/healthcheck returns hosted_runtime_healthcheck.v1",
                    "GET /hosting/studio-assets returns hosted_studio_assets.v1",
                    "GET /deploy/smoke-tests returns deployment_smoke_tests.v1",
                    "POST /deploy/smoke-tests/run validates hosted demo routes",
                    "POST /demo/domain-flow runs without external AI",
                    "runtime and domain behavior remain outside the hosting adapter",
                ],
                "non_goals": [
                    "no platform-specific deployment in this sprint",
                    "no visual redesign",
                    "no external LLM dependency",
                    "no business logic in hosting configuration",
                ],
                "metadata": {
                    "sprint": 60,
                    "epic": "Hosted Demo Path",
                    "business_logic": "runtime_only",
                    "platform_lock_in": False,
                },
            }
        )


def default_hosting_routes() -> tuple[HostingRoute, ...]:
    return (
        HostingRoute("health", "GET", "/health", "Runtime and adapter health."),
        HostingRoute("studio", "GET", "/studio", "ACA Studio web shell."),
        HostingRoute("runtime_status", "GET", "/runtime/status", "Runtime status summary."),
        HostingRoute("studio_binding", "GET", "/studio/binding", "Studio Runtime binding state."),
        HostingRoute("demo_domain_flow", "POST", "/demo/domain-flow", "Deterministic Domain Pack demo flow."),
        HostingRoute("public_demo_runtime_adapter", "GET", "/public-demo/runtime-adapter", "Public demo runtime adapter contract."),
        HostingRoute("public_demo_polish", "GET", "/public-demo/polish", "Public demo copy and presentation contract."),
        HostingRoute("hosting_target", "GET", "/hosting/target", "Platform-neutral hosting target contract."),
        HostingRoute("hosting_target_validate", "GET", "/hosting/target/validate", "Hosting target contract validation."),
        HostingRoute("hosted_runtime_healthcheck", "GET", "/hosting/healthcheck", "Hosted runtime healthcheck for public web deployments."),
        HostingRoute("hosted_runtime_healthcheck_validate", "GET", "/hosting/healthcheck/validate", "Hosted runtime healthcheck validation."),
        HostingRoute("hosted_studio_assets", "GET", "/hosting/studio-assets", "Hosted ACA Studio asset strategy."),
        HostingRoute("hosted_studio_assets_validate", "GET", "/hosting/studio-assets/validate", "Hosted ACA Studio asset validation."),
        HostingRoute("deployment_smoke_tests", "GET", "/deploy/smoke-tests", "Deployment smoke test plan for hosted demo readiness."),
        HostingRoute("deployment_smoke_tests_run", "POST", "/deploy/smoke-tests/run", "Run deployment smoke tests through REST adapter routes."),
        HostingRoute("deployment_smoke_tests_validate", "GET", "/deploy/smoke-tests/validate", "Validate deployment smoke test results."),
    )


def build_hosting_target_contract(
    *,
    app_name: str = "aca-public-web-demo",
    platform: str = "generic-python-web-service",
    public_base_url: str = "https://aca-demo.example.com",
    port_env: str = "PORT",
    fallback_port: int = 8765,
) -> Dict[str, Any]:
    return HostingTargetContract(
        app_name=app_name,
        platform=platform,
        public_base_url=public_base_url,
        port_env=port_env,
        fallback_port=fallback_port,
        routes=default_hosting_routes(),
    ).to_dict()


def validate_hosting_target_contract(
    *,
    project_root: str | Path = ".",
    contract: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = dict(contract or build_hosting_target_contract())
    root = Path(project_root)
    errors: list[str] = []

    if payload.get("contract") != HOSTING_TARGET_CONTRACT:
        errors.append("invalid hosting target contract")
    if payload.get("runtime", {}).get("external_ai_required") is not False:
        errors.append("hosted demo must not require external AI")
    if payload.get("runtime", {}).get("business_logic_location") != "runtime":
        errors.append("hosting target must keep business logic in runtime")
    process = payload.get("process", {})
    if process.get("host") != "0.0.0.0":
        errors.append("hosted process must bind to 0.0.0.0")
    if not process.get("port_env"):
        errors.append("hosted process must define a port environment variable")
    if payload.get("healthcheck", {}).get("path") != "/health":
        errors.append("hosting target must expose /health")

    routes = payload.get("routes") or []
    route_paths = {route.get("path") for route in routes if isinstance(route, Mapping)}
    for required_path in {"/health", "/studio", "/demo/domain-flow", "/hosting/target", "/hosting/studio-assets"}:
        if required_path not in route_paths:
            errors.append(f"missing required route: {required_path}")

    for relative in payload.get("required_files", []):
        if not (root / str(relative)).exists():
            errors.append(f"missing required file: {relative}")

    return {
        "valid": not errors,
        "errors": errors,
        "contract": sanitize(payload),
    }
