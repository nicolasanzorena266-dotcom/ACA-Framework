from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize
from aca_os.hosting_target_contract import build_hosting_target_contract, validate_hosting_target_contract
from aca_os.hosted_runtime_healthcheck import build_hosted_runtime_healthcheck, validate_hosted_runtime_healthcheck
from aca_os.hosted_studio_assets import build_hosted_studio_assets, validate_hosted_studio_assets
from aca_os.deployment_smoke_tests import build_deployment_smoke_test_plan


FIRST_PUBLIC_HOSTED_DEMO = "first_public_hosted_demo.v1"


@dataclass(frozen=True)
class PublicHostedDemoTarget:
    """First public hosted demo deployment target.

    This is intentionally a contract, not a platform deploy client. ACA stays
    deterministic and local-testable; external hosts only receive the process
    shape, required routes and smoke criteria needed to run the demo.
    """

    app_name: str = "aca-public-web-demo"
    platform: str = "render-web-service"
    public_base_url: str = "https://aca-public-web-demo.onrender.com"
    project_root: Path = Path(".")
    port_env: str = "PORT"
    fallback_port: int = 8765
    domain_pack_root: str = "examples/domain_packs"
    default_domain_pack: str = "example.customer_support"
    studio_path: str = "studio/index.html"

    def to_dict(self) -> Dict[str, Any]:
        public_base = self.public_base_url.rstrip("/")
        hosting = build_hosting_target_contract(
            app_name=self.app_name,
            platform=self.platform,
            public_base_url=public_base,
            port_env=self.port_env,
            fallback_port=self.fallback_port,
        )
        health = build_hosted_runtime_healthcheck(
            mode="hosted",
            project_root=self.project_root,
            public_base_url=public_base,
            port_env=self.port_env,
            fallback_port=self.fallback_port,
            default_domain_pack=self.default_domain_pack,
            domain_pack_root=self.domain_pack_root,
            studio_path=self.studio_path,
        )
        assets = build_hosted_studio_assets(
            project_root=self.project_root,
            public_base_url=public_base,
            studio_path=self.studio_path,
            fallback_route="/studio",
            api_base_route="/",
        )
        smoke = build_deployment_smoke_test_plan(
            project_root=self.project_root,
            public_base_url=public_base,
            domain_pack_root=self.domain_pack_root,
            default_domain_pack=self.default_domain_pack,
        )

        return sanitize(
            {
                "contract": FIRST_PUBLIC_HOSTED_DEMO,
                "status": "ready",
                "app": {
                    "name": self.app_name,
                    "surface": "ACA Studio",
                    "platform": self.platform,
                    "public_base_url": public_base,
                    "mode": "first-public-hosted-demo",
                },
                "runtime": {
                    "start_command": "python tools/aca_web.py --host 0.0.0.0",
                    "healthcheck_path": "/health",
                    "studio_path": "/studio",
                    "external_ai_required": False,
                    "business_logic_location": "runtime",
                    "interface_logic_location": "adapters_and_studio_shell",
                },
                "environment": {
                    self.port_env: str(self.fallback_port),
                    "ACA_HOST": "0.0.0.0",
                    "ACA_PUBLIC_BASE_URL": public_base,
                    "ACA_DOMAIN_PACK_ROOT": self.domain_pack_root,
                    "ACA_DEFAULT_DOMAIN_PACK": self.default_domain_pack,
                    "ACA_STUDIO_PATH": self.studio_path,
                },
                "public_urls": {
                    "root": public_base,
                    "studio": f"{public_base}/studio",
                    "health": f"{public_base}/health",
                    "runtime_status": f"{public_base}/runtime/status",
                    "hosted_healthcheck": f"{public_base}/hosting/healthcheck",
                    "studio_assets": f"{public_base}/hosting/studio-assets",
                    "smoke_tests": f"{public_base}/deploy/smoke-tests",
                    "first_demo_contract": f"{public_base}/hosted-demo/first",
                },
                "platform_targets": [
                    {
                        "id": "render-web-service",
                        "label": "Render Web Service",
                        "build_command": "python -m pytest -q",
                        "start_command": "python tools/aca_web.py --host 0.0.0.0",
                        "healthcheck_path": "/health",
                        "port_strategy": "PORT environment variable",
                    },
                    {
                        "id": "railway-service",
                        "label": "Railway Service",
                        "build_command": "python -m pytest -q",
                        "start_command": "python tools/aca_web.py --host 0.0.0.0",
                        "healthcheck_path": "/health",
                        "port_strategy": "PORT environment variable",
                    },
                    {
                        "id": "generic-python-web-service",
                        "label": "Generic Python Web Service",
                        "build_command": "python -m pytest -q",
                        "start_command": "python tools/aca_web.py --host 0.0.0.0",
                        "healthcheck_path": "/health",
                        "port_strategy": "PORT with fallback 8765",
                    },
                ],
                "required_routes": [
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
                    "/hosted-demo/first",
                    "/hosted-demo/first/validate",
                ],
                "deploy_checklist": [
                    "connect repository main branch to selected Python web host",
                    "set start command to python tools/aca_web.py --host 0.0.0.0",
                    "let the host provide PORT or set PORT=8765 for local-style hosts",
                    "configure healthcheck path as /health",
                    "open /studio after deploy becomes healthy",
                    "run deployment smoke tests against the public base URL",
                ],
                "local_verification": {
                    "command": "python tools/aca_web.py --host 127.0.0.1 --port 8765 --open",
                    "studio_url": "http://127.0.0.1:8765/studio",
                    "health_url": "http://127.0.0.1:8765/health",
                },
                "smoke_test": {
                    "contract": smoke["contract"],
                    "mode": smoke["mode"],
                    "test_count": smoke["test_count"],
                    "public_base_url": smoke["public_base_url"],
                    "run_endpoint": "/deploy/smoke-tests/run",
                    "validate_endpoint": "/deploy/smoke-tests/validate",
                },
                "readiness_refs": {
                    "hosting_target_contract": hosting,
                    "hosted_runtime_healthcheck": health,
                    "hosted_studio_assets": assets,
                },
                "acceptance_criteria": [
                    "public host starts ACA using the documented start command",
                    "GET /health returns status ok",
                    "GET /studio serves ACA Studio",
                    "GET /hosted-demo/first returns first_public_hosted_demo.v1",
                    "GET /hosted-demo/first/validate returns valid true before public deploy attempt",
                    "deployment smoke tests remain deterministic and do not require external AI",
                ],
                "non_goals": [
                    "no provider API automation",
                    "no secret management",
                    "no paid service dependency",
                    "no business logic in deployment configuration",
                ],
                "metadata": {"sprint": 64, "epic": "Hosted Demo Path"},
            }
        )


def build_first_public_hosted_demo(
    *,
    app_name: str = "aca-public-web-demo",
    platform: str = "render-web-service",
    public_base_url: str = "https://aca-public-web-demo.onrender.com",
    project_root: str | Path = ".",
    port_env: str = "PORT",
    fallback_port: int = 8765,
    domain_pack_root: str | Path = "examples/domain_packs",
    default_domain_pack: str = "example.customer_support",
    studio_path: str | Path = "studio/index.html",
) -> Dict[str, Any]:
    if not app_name:
        raise ValueError("app_name is required.")
    if not public_base_url:
        raise ValueError("public_base_url is required.")
    if fallback_port <= 0:
        raise ValueError("fallback_port must be positive.")
    return PublicHostedDemoTarget(
        app_name=app_name,
        platform=platform,
        public_base_url=public_base_url,
        project_root=Path(project_root),
        port_env=port_env,
        fallback_port=fallback_port,
        domain_pack_root=str(domain_pack_root),
        default_domain_pack=default_domain_pack,
        studio_path=str(studio_path),
    ).to_dict()


def validate_first_public_hosted_demo(
    *,
    project_root: str | Path = ".",
    demo: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = dict(demo or build_first_public_hosted_demo(project_root=project_root))
    errors: list[str] = []

    if payload.get("contract") != FIRST_PUBLIC_HOSTED_DEMO:
        errors.append("invalid first public hosted demo contract")
    if payload.get("runtime", {}).get("external_ai_required") is not False:
        errors.append("first public hosted demo must not require external AI")
    if payload.get("runtime", {}).get("business_logic_location") != "runtime":
        errors.append("first public hosted demo must keep business logic in runtime")
    if "/health" not in payload.get("required_routes", []):
        errors.append("first public hosted demo must expose /health")
    if "/studio" not in payload.get("required_routes", []):
        errors.append("first public hosted demo must expose /studio")
    public_base_url = payload.get("app", {}).get("public_base_url")
    if not isinstance(public_base_url, str) or not public_base_url.startswith(("http://", "https://")):
        errors.append("first public hosted demo public_base_url must be absolute")

    root = Path(project_root)
    for required_file in [
        "tools/aca_web.py",
        "studio/index.html",
        "deploy/public-web-demo.json",
        "deploy/hosting-target-contract.json",
        "deploy/deployment-smoke-tests.json",
        "deploy/first-public-hosted-demo.json",
    ]:
        if not (root / required_file).exists():
            errors.append(f"missing required public demo file: {required_file}")

    hosting_validation = validate_hosting_target_contract(project_root=root)
    health_validation = validate_hosted_runtime_healthcheck(project_root=root)
    asset_validation = validate_hosted_studio_assets(project_root=root)
    smoke_plan = build_deployment_smoke_test_plan(project_root=root)
    smoke_validation = {"valid": smoke_plan.get("contract") == "deployment_smoke_tests.v1" and smoke_plan.get("test_count", 0) >= 1}

    for label, validation in [
        ("hosting target", hosting_validation),
        ("hosted runtime healthcheck", health_validation),
        ("hosted Studio assets", asset_validation),
        ("deployment smoke test plan", smoke_validation),
    ]:
        if validation.get("valid") is not True:
            errors.append(f"{label} validation failed")

    return sanitize(
        {
            "valid": not errors,
            "errors": errors,
            "contract": "first_public_hosted_demo_validation.v1",
            "demo": payload,
            "checks": {
                "hosting_target": hosting_validation.get("valid") is True,
                "hosted_runtime_healthcheck": health_validation.get("valid") is True,
                "hosted_studio_assets": asset_validation.get("valid") is True,
                "deployment_smoke_tests": smoke_validation.get("valid") is True,
            },
            "project_root": str(project_root),
        }
    )
