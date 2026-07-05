from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize
from aca_os.first_public_hosted_demo import build_first_public_hosted_demo, validate_first_public_hosted_demo
from aca_os.hosting_target_contract import build_hosting_target_contract


RENDER_DEPLOYMENT_CONFIG = "render_deployment_config.v1"
RENDER_DEPLOYMENT_VALIDATION = "render_deployment_validation.v1"


@dataclass(frozen=True)
class RenderDeploymentConfig:
    """Render-specific deployment configuration contract for ACA Studio.

    This object describes how Render should run ACA. It does not deploy,
    authenticate, or call Render APIs. Deployment remains an external operation;
    ACA only owns deterministic configuration and validation.
    """

    service_name: str = "aca-public-web-demo"
    repo_branch: str = "main"
    region: str = "oregon"
    plan: str = "free"
    runtime: str = "python"
    build_command: str = "python -m pytest -q"
    start_command: str = "python tools/aca_web.py --host 0.0.0.0"
    healthcheck_path: str = "/health"
    public_base_url: str = "https://aca-public-web-demo.onrender.com"
    port_env: str = "PORT"
    fallback_port: int = 8765
    domain_pack_root: str = "examples/domain_packs"
    default_domain_pack: str = "example.customer_support"
    studio_path: str = "studio/index.html"

    def to_dict(self) -> Dict[str, Any]:
        public_base = self.public_base_url.rstrip("/")
        hosting = build_hosting_target_contract(
            app_name=self.service_name,
            platform="render-web-service",
            public_base_url=public_base,
            port_env=self.port_env,
            fallback_port=self.fallback_port,
        )
        hosted_demo = build_first_public_hosted_demo(
            app_name=self.service_name,
            platform="render-web-service",
            public_base_url=public_base,
            port_env=self.port_env,
            fallback_port=self.fallback_port,
            domain_pack_root=self.domain_pack_root,
            default_domain_pack=self.default_domain_pack,
            studio_path=self.studio_path,
        )
        return sanitize(
            {
                "contract": RENDER_DEPLOYMENT_CONFIG,
                "status": "ready",
                "platform": "render",
                "service": {
                    "name": self.service_name,
                    "type": "web",
                    "runtime": self.runtime,
                    "region": self.region,
                    "plan": self.plan,
                    "branch": self.repo_branch,
                },
                "process": {
                    "build_command": self.build_command,
                    "start_command": self.start_command,
                    "healthcheck_path": self.healthcheck_path,
                    "host": "0.0.0.0",
                    "port_env": self.port_env,
                    "fallback_port": self.fallback_port,
                },
                "environment": {
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
                    "first_demo": f"{public_base}/hosted-demo/first",
                    "smoke_tests": f"{public_base}/deploy/smoke-tests",
                },
                "required_files": [
                    "render.yaml",
                    "tools/aca_web.py",
                    "studio/index.html",
                    "deploy/render-deployment.json",
                    "deploy/first-public-hosted-demo.json",
                    "deploy/hosting-target-contract.json",
                    "aca_os/runtime_rest.py",
                    "aca_os/runtime_api_endpoints.py",
                    "aca_os/first_public_hosted_demo.py",
                    "pyproject.toml",
                ],
                "render_blueprint": {
                    "schema_file": "render.yaml",
                    "service_type": "web",
                    "env": "python",
                    "auto_deploy": True,
                    "health_check_path": self.healthcheck_path,
                    "start_command": self.start_command,
                    "build_command": self.build_command,
                },
                "deploy_steps": [
                    "create a new Render Blueprint from the GitHub repository",
                    "select the main branch",
                    "let Render read render.yaml",
                    "wait for build command to finish",
                    "wait for /health to become healthy",
                    "open /studio",
                    "run /deploy/smoke-tests/run after the service is reachable",
                ],
                "readiness_refs": {
                    "hosting_target_contract": hosting,
                    "first_public_hosted_demo": hosted_demo,
                },
                "acceptance_criteria": [
                    "render.yaml exists at repository root",
                    "Render start command binds to 0.0.0.0 and uses the host-provided PORT",
                    "GET /health remains the healthcheck path",
                    "ACA Studio is served at /studio",
                    "no external AI or paid dependency is required for the demo runtime",
                ],
                "non_goals": [
                    "no Render API call",
                    "no secret management",
                    "no provider lock-in beyond the blueprint file",
                    "no business logic in render.yaml",
                ],
                "metadata": {"sprint": 65, "epic": "Public Deployment Execution"},
            }
        )


def build_render_deployment_config(
    *,
    service_name: str = "aca-public-web-demo",
    repo_branch: str = "main",
    region: str = "oregon",
    plan: str = "free",
    public_base_url: str = "https://aca-public-web-demo.onrender.com",
    port_env: str = "PORT",
    fallback_port: int = 8765,
    domain_pack_root: str = "examples/domain_packs",
    default_domain_pack: str = "example.customer_support",
    studio_path: str = "studio/index.html",
) -> Dict[str, Any]:
    if not service_name:
        raise ValueError("service_name is required.")
    if fallback_port <= 0:
        raise ValueError("fallback_port must be positive.")
    return RenderDeploymentConfig(
        service_name=service_name,
        repo_branch=repo_branch,
        region=region,
        plan=plan,
        public_base_url=public_base_url,
        port_env=port_env,
        fallback_port=fallback_port,
        domain_pack_root=domain_pack_root,
        default_domain_pack=default_domain_pack,
        studio_path=studio_path,
    ).to_dict()


def render_blueprint_yaml(config: Mapping[str, Any] | None = None) -> str:
    payload = dict(config or build_render_deployment_config())
    service = payload["service"]
    process = payload["process"]
    env = payload["environment"]
    lines = [
        "services:",
        f"  - type: {service['type']}",
        f"    name: {service['name']}",
        f"    runtime: {service['runtime']}",
        f"    plan: {service['plan']}",
        f"    region: {service['region']}",
        f"    branch: {service['branch']}",
        "    autoDeploy: true",
        f"    buildCommand: {process['build_command']}",
        f"    startCommand: {process['start_command']}",
        f"    healthCheckPath: {process['healthcheck_path']}",
        "    envVars:",
    ]
    for key, value in env.items():
        lines.extend([f"      - key: {key}", f"        value: {value}"])
    return "\n".join(lines) + "\n"


def validate_render_deployment_config(
    *,
    project_root: str | Path = ".",
    config: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    root = Path(project_root)
    payload = dict(config or build_render_deployment_config())
    errors: list[str] = []

    if payload.get("contract") != RENDER_DEPLOYMENT_CONFIG:
        errors.append("invalid render deployment config contract")
    if payload.get("platform") != "render":
        errors.append("platform must be render")
    process = payload.get("process", {})
    if "python tools/aca_web.py" not in str(process.get("start_command", "")):
        errors.append("Render start command must launch tools/aca_web.py")
    if "--host 0.0.0.0" not in str(process.get("start_command", "")):
        errors.append("Render start command must bind to 0.0.0.0")
    if process.get("healthcheck_path") != "/health":
        errors.append("Render healthcheck path must be /health")
    if process.get("port_env") != "PORT":
        errors.append("Render port environment variable must be PORT")

    required_files = list(payload.get("required_files", []))
    missing = [path for path in required_files if not (root / path).exists()]
    errors.extend([f"missing required file: {path}" for path in missing])

    blueprint_path = root / "render.yaml"
    if blueprint_path.exists():
        text = blueprint_path.read_text(encoding="utf-8")
        required_fragments = [
            "services:",
            "type: web",
            "runtime: python",
            "startCommand: python tools/aca_web.py --host 0.0.0.0",
            "healthCheckPath: /health",
            "key: ACA_PUBLIC_BASE_URL",
        ]
        for fragment in required_fragments:
            if fragment not in text:
                errors.append(f"render.yaml missing fragment: {fragment}")
    else:
        errors.append("missing required file: render.yaml")

    first_demo_validation = validate_first_public_hosted_demo(project_root=root)
    if not first_demo_validation.get("valid"):
        errors.append("first public hosted demo validation failed")

    return sanitize(
        {
            "contract": RENDER_DEPLOYMENT_VALIDATION,
            "valid": not errors,
            "errors": errors,
            "checks": {
                "contract": payload.get("contract") == RENDER_DEPLOYMENT_CONFIG,
                "platform": payload.get("platform") == "render",
                "start_command": not any("start command" in error for error in errors),
                "healthcheck": process.get("healthcheck_path") == "/health",
                "required_files": not missing,
                "render_yaml": blueprint_path.exists(),
                "first_public_hosted_demo": bool(first_demo_validation.get("valid")),
            },
            "metadata": {"sprint": 65, "epic": "Public Deployment Execution"},
        }
    )
