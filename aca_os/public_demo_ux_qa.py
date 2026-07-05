from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize
from aca_os.public_demo_polish import build_public_demo_polish
from aca_os.studio_visual_design import build_studio_visual_design_system


PUBLIC_DEMO_UX_QA_CONTRACT = "public_demo_ux_qa.v1"
PUBLIC_DEMO_UX_QA_VALIDATION = "public_demo_ux_qa_validation.v1"


@dataclass(frozen=True)
class PublicDemoUXQACheck:
    """One deterministic UX QA checkpoint for the hosted public demo surface."""

    id: str
    area: str
    expectation: str
    evidence: str
    severity: str = "must"

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "area": self.area,
            "expectation": self.expectation,
            "evidence": self.evidence,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class PublicDemoUXQAReport:
    """Sprint 68 UX QA contract for ACA Studio public demo.

    This object audits public demo experience expectations only. It does not run
    runtime business behavior and it does not classify user input.
    """

    checks: tuple[PublicDemoUXQACheck, ...]
    public_base_url: str = "https://aca-public-web-demo.onrender.com"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        polish = build_public_demo_polish()
        design = build_studio_visual_design_system()
        checks = [check.to_dict() for check in self.checks]
        failed = [check for check in checks if check.get("severity") == "blocker"]
        return sanitize(
            {
                "contract": PUBLIC_DEMO_UX_QA_CONTRACT,
                "status": "ready" if not failed else "blocked",
                "product": {
                    "name": "ACA Studio",
                    "surface": "public_hosted_demo",
                    "visual_direction": design.get("product", {}).get("visual_direction"),
                    "experience_goal": "first_user_can_run_demo_and_understand_runtime_state",
                },
                "public_base_url": self.public_base_url,
                "entry_points": {
                    "studio": "/studio",
                    "health": "/health",
                    "runtime_status": "/runtime/status",
                    "domain_flow": "/demo/domain-flow",
                    "polish": "/public-demo/polish",
                    "ux_qa": "/public-demo/ux-qa",
                    "smoke_tests": "/deploy/smoke-tests",
                },
                "copy_baseline": {
                    "hero_title": polish.get("hero", {}).get("title"),
                    "primary_action": polish.get("hero", {}).get("primary_action"),
                    "ready_state": polish.get("states", {}).get("ready"),
                    "error_state": polish.get("states", {}).get("error"),
                },
                "qa_summary": {
                    "check_count": len(checks),
                    "areas": sorted({check["area"] for check in checks}),
                    "blockers": len(failed),
                    "business_logic_location": "runtime",
                    "external_ai_required": False,
                    "trace_visible": True,
                    "domain_pack_visible": True,
                },
                "checks": checks,
                "acceptance_criteria": [
                    "A first-time visitor sees ACA Studio, the runtime state and the main demo action without reading docs.",
                    "The demo flow exposes output, active domain context and trace/metrics in separate panels.",
                    "Hosted errors are legible and do not expose Python tracebacks.",
                    "The Studio shell never owns domain or runtime business logic.",
                    "The public URL can be validated with the Sprint 66 smoke test command.",
                ],
                "non_goals": [
                    "no visual redesign beyond QA polish",
                    "no external LLM dependency",
                    "no provider lock-in beyond Render-first config",
                    "no runtime core rewrite",
                ],
                "metadata": {"sprint": 68, "epic": "Public Deployment Execution", **dict(self.metadata)},
            }
        )


def build_public_demo_ux_qa(
    *,
    public_base_url: str = "https://aca-public-web-demo.onrender.com",
) -> Dict[str, Any]:
    checks = (
        PublicDemoUXQACheck(
            id="landing_identity",
            area="landing",
            expectation="ACA Studio name and runtime positioning are visible immediately.",
            evidence="Studio title, brand area and hero copy use ACA Studio consistently.",
        ),
        PublicDemoUXQACheck(
            id="primary_action_visible",
            area="first_run",
            expectation="The main demo action is available without scrolling or setup decisions.",
            evidence="Primary CTA remains 'Ejecutar demo'.",
        ),
        PublicDemoUXQACheck(
            id="runtime_state_visible",
            area="runtime_state",
            expectation="Runtime readiness is visible before and after execution.",
            evidence="Status pill and connection label surface ready/error states.",
        ),
        PublicDemoUXQACheck(
            id="domain_context_visible",
            area="domain_packs",
            expectation="Loaded Domain Packs are visible to explain the active world.",
            evidence="Sidebar modules and context title expose customer_support and operations_basic.",
        ),
        PublicDemoUXQACheck(
            id="trace_metrics_visible",
            area="observability",
            expectation="Trace and metrics remain visible as Runtime evidence.",
            evidence="Bottom panel keeps trace/metrics separate from normal output.",
        ),
        PublicDemoUXQACheck(
            id="error_copy_legible",
            area="errors",
            expectation="Public failures are readable and do not hide behind raw tracebacks.",
            evidence="Hosted hardening error envelope and public demo copy provide hints.",
        ),
        PublicDemoUXQACheck(
            id="business_logic_boundary",
            area="architecture",
            expectation="Studio QA does not own domain or runtime decisions.",
            evidence="QA contract states business_logic_location=runtime and external_ai_required=false.",
        ),
    )
    return PublicDemoUXQAReport(checks=checks, public_base_url=public_base_url).to_dict()


def validate_public_demo_ux_qa(
    *,
    project_root: str | Path = ".",
    report: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    root = Path(project_root)
    payload = dict(report or build_public_demo_ux_qa())
    errors: list[str] = []

    if payload.get("contract") != PUBLIC_DEMO_UX_QA_CONTRACT:
        errors.append("invalid public demo UX QA contract")
    if payload.get("product", {}).get("name") != "ACA Studio":
        errors.append("public demo UX QA must target ACA Studio")
    if payload.get("qa_summary", {}).get("business_logic_location") != "runtime":
        errors.append("public demo UX QA must keep business logic in runtime")
    if payload.get("qa_summary", {}).get("external_ai_required") is not False:
        errors.append("public demo UX QA must not require external AI")
    if payload.get("qa_summary", {}).get("trace_visible") is not True:
        errors.append("public demo UX QA must require visible trace")
    if payload.get("qa_summary", {}).get("domain_pack_visible") is not True:
        errors.append("public demo UX QA must require visible domain pack context")
    if len(payload.get("checks") or []) < 7:
        errors.append("public demo UX QA must include at least seven checks")

    required_areas = {"landing", "first_run", "runtime_state", "domain_packs", "observability", "errors", "architecture"}
    areas = set(payload.get("qa_summary", {}).get("areas") or [])
    missing_areas = sorted(required_areas - areas)
    for area in missing_areas:
        errors.append(f"missing UX QA area: {area}")

    required_files = [
        "studio/index.html",
        "aca_os/public_demo_polish.py",
        "aca_os/studio_visual_design.py",
        "aca_os/runtime_rest.py",
        "aca_os/public_url_smoke_test.py",
        "deploy/public-url-smoke-test.json",
    ]
    for required in required_files:
        if not (root / required).exists():
            errors.append(f"missing required file: {required}")

    return sanitize(
        {
            "contract": PUBLIC_DEMO_UX_QA_VALIDATION,
            "valid": not errors,
            "status": "valid" if not errors else "invalid",
            "errors": errors,
            "checked_files": required_files,
            "report": payload,
        }
    )
