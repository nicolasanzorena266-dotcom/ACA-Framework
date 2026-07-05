from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize
from aca_os.first_public_hosted_demo import build_first_public_hosted_demo, validate_first_public_hosted_demo
from aca_os.hosted_runtime_hardening import build_hosted_runtime_hardening, validate_hosted_runtime_hardening
from aca_os.hosted_runtime_healthcheck import build_hosted_runtime_healthcheck, validate_hosted_runtime_healthcheck
from aca_os.hosted_studio_assets import build_hosted_studio_assets, validate_hosted_studio_assets
from aca_os.public_demo_ux_qa import build_public_demo_ux_qa, validate_public_demo_ux_qa
from aca_os.public_url_smoke_test import build_public_url_smoke_test_plan
from aca_os.render_deployment_config import build_render_deployment_config, validate_render_deployment_config


PUBLIC_DEMO_RELEASE_CANDIDATE = "public_demo_release_candidate.v1"
PUBLIC_DEMO_RELEASE_CANDIDATE_VALIDATION = "public_demo_release_candidate_validation.v1"


@dataclass(frozen=True)
class PublicDemoReleaseCandidate:
    """Public demo release candidate contract.

    This module does not deploy ACA. It freezes the deterministic release surface
    that must be true before a human starts the first hosted Render deployment.
    """

    release_id: str = "public-demo-rc1"
    public_base_url: str = "https://aca-public-web-demo.onrender.com"
    platform: str = "render-web-service"
    project_root: Path = Path(".")
    default_domain_pack: str = "example.customer_support"
    domain_pack_root: str = "examples/domain_packs"
    studio_path: str = "studio/index.html"

    def to_dict(self) -> Dict[str, Any]:
        base_url = self.public_base_url.rstrip("/")
        render_config = build_render_deployment_config(
            public_base_url=base_url,
            default_domain_pack=self.default_domain_pack,
            domain_pack_root=self.domain_pack_root,
            studio_path=self.studio_path,
        )
        first_demo = build_first_public_hosted_demo(
            public_base_url=base_url,
            project_root=self.project_root,
            platform=self.platform,
            default_domain_pack=self.default_domain_pack,
            domain_pack_root=self.domain_pack_root,
            studio_path=self.studio_path,
        )
        healthcheck = build_hosted_runtime_healthcheck(
            mode="hosted",
            project_root=self.project_root,
            public_base_url=base_url,
            default_domain_pack=self.default_domain_pack,
            domain_pack_root=self.domain_pack_root,
            studio_path=self.studio_path,
        )
        assets = build_hosted_studio_assets(
            project_root=self.project_root,
            public_base_url=base_url,
            studio_path=self.studio_path,
        )
        hardening = build_hosted_runtime_hardening(mode="hosted", platform=self.platform)
        ux_qa = build_public_demo_ux_qa(public_base_url=base_url)
        public_smoke = build_public_url_smoke_test_plan(public_base_url=base_url)

        return sanitize(
            {
                "contract": PUBLIC_DEMO_RELEASE_CANDIDATE,
                "status": "release-candidate",
                "release": {
                    "id": self.release_id,
                    "label": "ACA Studio Public Demo RC1",
                    "surface": "ACA Studio",
                    "target_platform": self.platform,
                    "public_base_url": base_url,
                    "version_state": "0.3.0-sprint70",
                    "external_ai_required": False,
                    "deterministic_runtime": True,
                },
                "entrypoints": {
                    "root": base_url,
                    "studio": f"{base_url}/studio",
                    "health": f"{base_url}/health",
                    "runtime_status": f"{base_url}/runtime/status",
                    "demo_flow": f"{base_url}/demo/domain-flow",
                    "public_smoke": f"{base_url}/deploy/smoke-tests/run",
                    "release_candidate": f"{base_url}/public-demo/release-candidate",
                    "release_candidate_validation": f"{base_url}/public-demo/release-candidate/validate",
                },
                "render": {
                    "service_name": render_config["service"]["name"],
                    "plan": render_config["service"]["plan"],
                    "build_command": render_config["process"]["build_command"],
                    "start_command": render_config["process"]["start_command"],
                    "healthcheck_path": render_config["process"]["healthcheck_path"],
                    "cold_start_expected": True,
                },
                "runtime": {
                    "mode": "hosted",
                    "default_domain_pack": self.default_domain_pack,
                    "domain_pack_root": self.domain_pack_root,
                    "studio_path": self.studio_path,
                    "business_logic_location": "runtime",
                    "interface_logic_location": "REST and ACA Studio adapters",
                },
                "release_gates": [
                    {
                        "id": "render_config_valid",
                        "label": "Render deployment config validates",
                        "required": True,
                        "validation_endpoint": "/deploy/render/validate",
                    },
                    {
                        "id": "hosted_healthcheck_valid",
                        "label": "Hosted Runtime healthcheck validates",
                        "required": True,
                        "validation_endpoint": "/hosting/healthcheck/validate",
                    },
                    {
                        "id": "studio_assets_valid",
                        "label": "Hosted Studio assets validate",
                        "required": True,
                        "validation_endpoint": "/hosting/studio-assets/validate",
                    },
                    {
                        "id": "runtime_hardening_valid",
                        "label": "Hosted Runtime hardening validates",
                        "required": True,
                        "validation_endpoint": "/hosting/hardening/validate",
                    },
                    {
                        "id": "ux_qa_valid",
                        "label": "Public Demo UX QA validates",
                        "required": True,
                        "validation_endpoint": "/public-demo/ux-qa/validate",
                    },
                    {
                        "id": "first_public_demo_valid",
                        "label": "First public hosted demo validates",
                        "required": True,
                        "validation_endpoint": "/hosted-demo/first/validate",
                    },
                    {
                        "id": "public_url_smoke_ready",
                        "label": "Public URL smoke test plan is ready for the hosted URL",
                        "required": True,
                        "validation_endpoint": "local: tools/aca_smoke_url.py <public-url>",
                    },
                ],
                "public_smoke_plan": {
                    "contract": public_smoke["contract"],
                    "check_count": public_smoke["check_count"],
                    "public_base_url": public_smoke["public_base_url"],
                    "cold_start_note": public_smoke["cold_start_note"],
                },
                "manual_deploy_steps": [
                    "open Render and create a new Web Service from the ACA-Framework repository",
                    "select branch main",
                    "use build command: python -m pytest -q",
                    "use start command: python tools/aca_web.py --host 0.0.0.0",
                    "set healthcheck path to /health",
                    "wait for the service to become healthy",
                    "open /studio from the Render public URL",
                    "run tools/aca_smoke_url.py against the public URL",
                ],
                "acceptance_criteria": [
                    "release candidate validates all local deployment gates",
                    "public URL smoke test plan is ready before deploy",
                    "Render config is present and references the hosted start command",
                    "ACA Studio remains the public surface",
                    "hosted runtime remains deterministic and offline-capable",
                    "no LLM or external AI dependency is introduced",
                ],
                "readiness_refs": {
                    "render_deployment_config": render_config,
                    "first_public_hosted_demo": first_demo,
                    "hosted_runtime_healthcheck": healthcheck,
                    "hosted_studio_assets": assets,
                    "hosted_runtime_hardening": hardening,
                    "public_demo_ux_qa": ux_qa,
                },
                "non_goals": [
                    "no provider API automation",
                    "no production SLA",
                    "no paid hosting requirement",
                    "no visual redesign",
                    "no runtime core rewrite",
                ],
                "metadata": {"sprint": 69, "epic": "Public Deployment Execution"},
            }
        )


def build_public_demo_release_candidate(
    *,
    release_id: str = "public-demo-rc1",
    public_base_url: str = "https://aca-public-web-demo.onrender.com",
    platform: str = "render-web-service",
    project_root: str | Path = ".",
    default_domain_pack: str = "example.customer_support",
    domain_pack_root: str | Path = "examples/domain_packs",
    studio_path: str | Path = "studio/index.html",
) -> Dict[str, Any]:
    if not release_id:
        raise ValueError("release_id is required.")
    if not public_base_url:
        raise ValueError("public_base_url is required.")
    if not str(public_base_url).startswith(("http://", "https://")):
        raise ValueError("public_base_url must be absolute.")
    return PublicDemoReleaseCandidate(
        release_id=release_id,
        public_base_url=public_base_url,
        platform=platform,
        project_root=Path(project_root),
        default_domain_pack=default_domain_pack,
        domain_pack_root=str(domain_pack_root),
        studio_path=str(studio_path),
    ).to_dict()


def validate_public_demo_release_candidate(
    *,
    project_root: str | Path = ".",
    candidate: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    root = Path(project_root)
    payload = dict(candidate or build_public_demo_release_candidate(project_root=root))
    errors: list[str] = []

    if payload.get("contract") != PUBLIC_DEMO_RELEASE_CANDIDATE:
        errors.append("invalid public demo release candidate contract")
    if payload.get("status") != "release-candidate":
        errors.append("public demo release candidate must use release-candidate status")
    release = payload.get("release", {}) if isinstance(payload.get("release"), Mapping) else {}
    if release.get("surface") != "ACA Studio":
        errors.append("release candidate must expose ACA Studio as public surface")
    if release.get("external_ai_required") is not False:
        errors.append("release candidate must not require external AI")
    if release.get("deterministic_runtime") is not True:
        errors.append("release candidate must keep deterministic runtime true")

    required_files = [
        "render.yaml",
        "tools/aca_web.py",
        "tools/aca_smoke_url.py",
        "studio/index.html",
        "deploy/render-deployment.json",
        "deploy/public-url-smoke-test.json",
        "deploy/public-demo-release-candidate.json",
        "docs/RENDER_DEPLOYMENT.md",
        "docs/PUBLIC_DEMO_RELEASE_CANDIDATE.md",
    ]
    missing_files = [path for path in required_files if not (root / path).exists()]
    for path in missing_files:
        errors.append(f"missing required release candidate file: {path}")

    validations = {
        "render_config": validate_render_deployment_config(project_root=root),
        "hosted_runtime_healthcheck": validate_hosted_runtime_healthcheck(project_root=root),
        "hosted_studio_assets": validate_hosted_studio_assets(project_root=root),
        "hosted_runtime_hardening": validate_hosted_runtime_hardening(project_root=root),
        "public_demo_ux_qa": validate_public_demo_ux_qa(project_root=root),
        "first_public_hosted_demo": validate_first_public_hosted_demo(project_root=root),
    }
    for label, validation in validations.items():
        if validation.get("valid") is not True:
            errors.append(f"{label} validation failed")

    gates = payload.get("release_gates", [])
    required_gate_ids = {gate.get("id") for gate in gates if isinstance(gate, Mapping) and gate.get("required") is True}
    expected_gate_ids = {
        "render_config_valid",
        "hosted_healthcheck_valid",
        "studio_assets_valid",
        "runtime_hardening_valid",
        "ux_qa_valid",
        "first_public_demo_valid",
        "public_url_smoke_ready",
    }
    missing_gates = sorted(expected_gate_ids - required_gate_ids)
    for gate_id in missing_gates:
        errors.append(f"missing required release gate: {gate_id}")

    return sanitize(
        {
            "contract": PUBLIC_DEMO_RELEASE_CANDIDATE_VALIDATION,
            "valid": not errors,
            "errors": errors,
            "candidate": payload,
            "checks": {label: validation.get("valid") is True for label, validation in validations.items()},
            "required_files": required_files,
            "missing_files": missing_files,
            "project_root": str(project_root),
        }
    )
