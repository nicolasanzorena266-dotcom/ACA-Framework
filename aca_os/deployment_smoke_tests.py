from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize


DEPLOYMENT_SMOKE_TESTS = "deployment_smoke_tests.v1"
DEPLOYMENT_SMOKE_RESULTS = "deployment_smoke_results.v1"


@dataclass(frozen=True)
class DeploymentSmokeTest:
    """One in-process deployment smoke check against the REST adapter."""

    id: str
    method: str
    path: str
    purpose: str
    required: bool = True
    expected_status_code: int = 200
    expected_contract: str | None = None
    expected_payload_field: str | None = None
    expected_payload_value: Any | None = None
    query: Mapping[str, Any] = field(default_factory=dict)
    body: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "id": self.id,
                "method": self.method.upper(),
                "path": self.path,
                "purpose": self.purpose,
                "required": self.required,
                "expected_status_code": self.expected_status_code,
                "expected_contract": self.expected_contract,
                "expected_payload_field": self.expected_payload_field,
                "expected_payload_value": self.expected_payload_value,
                "query": dict(self.query),
                "body": dict(self.body),
            }
        )


def default_deployment_smoke_tests(
    *,
    project_root: str | Path = ".",
    public_base_url: str = "https://aca-demo.example.com",
    domain_pack_root: str | Path = "examples/domain_packs",
    default_domain_pack: str = "example.customer_support",
) -> tuple[DeploymentSmokeTest, ...]:
    root = str(project_root)
    domain_root = str(domain_pack_root)
    return (
        DeploymentSmokeTest(
            "platform_health",
            "GET",
            "/health",
            "Platform-facing health endpoint returns a stable ok status.",
            expected_payload_field="status",
            expected_payload_value="ok",
        ),
        DeploymentSmokeTest(
            "runtime_status",
            "GET",
            "/runtime/status",
            "Runtime status endpoint can instantiate the deterministic runtime.",
            expected_payload_field="status",
            expected_payload_value="ready",
        ),
        DeploymentSmokeTest(
            "studio_bootstrap",
            "GET",
            "/studio/bootstrap",
            "Studio bootstrap endpoint returns a browser-ready contract.",
            expected_contract="studio_api_integration.v1",
        ),
        DeploymentSmokeTest(
            "studio_binding",
            "GET",
            "/studio/binding",
            "Studio Runtime binding can assemble state, domain context, trace and metrics.",
            query={"root": domain_root},
            expected_contract="studio_runtime_binding.v1",
        ),
        DeploymentSmokeTest(
            "hosting_target_validation",
            "GET",
            "/hosting/target/validate",
            "Hosting target configuration validates before deployment.",
            query={"project_root": root},
            expected_payload_field="valid",
            expected_payload_value=True,
        ),
        DeploymentSmokeTest(
            "hosted_runtime_healthcheck_validation",
            "GET",
            "/hosting/healthcheck/validate",
            "Hosted runtime healthcheck validates against project files.",
            query={"project_root": root},
            expected_payload_field="valid",
            expected_payload_value=True,
        ),
        DeploymentSmokeTest(
            "hosted_studio_assets_validation",
            "GET",
            "/hosting/studio-assets/validate",
            "Hosted Studio assets validate before a public demo.",
            query={"project_root": root},
            expected_payload_field="valid",
            expected_payload_value=True,
        ),
        DeploymentSmokeTest(
            "first_public_hosted_demo",
            "GET",
            "/hosted-demo/first",
            "First public hosted demo contract is exposed before deployment.",
            expected_contract="first_public_hosted_demo.v1",
        ),
        DeploymentSmokeTest(
            "first_public_hosted_demo_validation",
            "GET",
            "/hosted-demo/first/validate",
            "First public hosted demo validates required hosted artifacts.",
            expected_payload_field="valid",
            expected_payload_value=True,
        ),
        DeploymentSmokeTest(
            "demo_domain_flow",
            "POST",
            "/demo/domain-flow",
            "Default Domain Pack demo flow runs without external AI.",
            body={
                "message": "Necesito revisar un caso de soporte",
                "conversation_id": "deployment-smoke-demo",
                "root": domain_root,
                "pack_name": default_domain_pack,
            },
            expected_contract="demo_domain_runtime_flow.v1",
        ),
    )


def build_deployment_smoke_test_plan(
    *,
    project_root: str | Path = ".",
    public_base_url: str = "https://aca-demo.example.com",
    domain_pack_root: str | Path = "examples/domain_packs",
    default_domain_pack: str = "example.customer_support",
) -> Dict[str, Any]:
    tests = default_deployment_smoke_tests(
        project_root=project_root,
        public_base_url=public_base_url,
        domain_pack_root=domain_pack_root,
        default_domain_pack=default_domain_pack,
    )
    return sanitize(
        {
            "contract": DEPLOYMENT_SMOKE_TESTS,
            "status": "ready",
            "surface": "ACA Studio hosted demo",
            "public_base_url": public_base_url.rstrip("/"),
            "mode": "in_process_rest_adapter_smoke_tests",
            "test_count": len(tests),
            "tests": [test.to_dict() for test in tests],
            "coverage": {
                "platform_health": "/health",
                "runtime": "/runtime/status",
                "studio": "/studio/bootstrap and /studio/binding",
                "hosting_config": "/hosting/target/validate",
                "hosted_healthcheck": "/hosting/healthcheck/validate",
                "assets": "/hosting/studio-assets/validate",
                "demo_flow": "/demo/domain-flow",
                "first_public_hosted_demo": "/hosted-demo/first and /hosted-demo/first/validate",
            },
            "acceptance_criteria": [
                "all required smoke tests pass before a public hosted demo",
                "smoke tests run through REST adapter routes instead of component internals",
                "health, runtime, Studio, assets, hosting config, first public demo and demo flow are covered",
                "failures return explicit diagnostic rows instead of silent deployment uncertainty",
            ],
            "non_goals": [
                "no external hosting platform call",
                "no public network call",
                "no network socket requirement",
                "no visual redesign",
                "no external AI dependency",
            ],
            "metadata": {"sprint": 64, "epic": "Hosted Demo Path"},
        }
    )


def run_deployment_smoke_tests(
    *,
    project_root: str | Path = ".",
    public_base_url: str = "https://aca-demo.example.com",
    domain_pack_root: str | Path = "examples/domain_packs",
    default_domain_pack: str = "example.customer_support",
    rest_api: Any | None = None,
) -> Dict[str, Any]:
    if rest_api is None:
        from aca_os.runtime_rest import RuntimeRESTAPI

        rest_api = RuntimeRESTAPI()

    plan = build_deployment_smoke_test_plan(
        project_root=project_root,
        public_base_url=public_base_url,
        domain_pack_root=domain_pack_root,
        default_domain_pack=default_domain_pack,
    )
    executable_tests = default_deployment_smoke_tests(
        project_root=project_root,
        public_base_url=public_base_url,
        domain_pack_root=domain_pack_root,
        default_domain_pack=default_domain_pack,
    )
    rows = []
    for test in executable_tests:
        spec = test.to_dict()
        response = rest_api.route(test.method, test.path, query=test.query, body=test.body)
        payload = response.payload
        errors = _evaluate_response(spec, response.status_code, payload)
        rows.append(
            sanitize(
                {
                    "id": test.id,
                    "method": test.method.upper(),
                    "path": test.path,
                    "required": test.required,
                    "passed": not errors,
                    "status_code": response.status_code,
                    "errors": errors,
                    "observed_contract": payload.get("contract") if isinstance(payload, Mapping) else None,
                    "observed_status": payload.get("status") if isinstance(payload, Mapping) else None,
                }
            )
        )

    required_failures = [row for row in rows if row["required"] and not row["passed"]]
    return sanitize(
        {
            "contract": DEPLOYMENT_SMOKE_RESULTS,
            "valid": not required_failures,
            "status": "ok" if not required_failures else "failed",
            "summary": {
                "total": len(rows),
                "passed": sum(1 for row in rows if row["passed"]),
                "failed": sum(1 for row in rows if not row["passed"]),
                "required_failures": len(required_failures),
            },
            "results": rows,
            "plan": plan,
        }
    )


def validate_deployment_smoke_tests(
    *,
    project_root: str | Path = ".",
    result: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = dict(result or run_deployment_smoke_tests(project_root=project_root))
    errors: list[str] = []

    if payload.get("contract") != DEPLOYMENT_SMOKE_RESULTS:
        errors.append("invalid deployment smoke test result contract")
    if payload.get("valid") is not True:
        errors.append("deployment smoke tests have required failures")
    for row in payload.get("results", []):
        if isinstance(row, Mapping) and row.get("required") is not False and row.get("passed") is not True:
            errors.append(f"required smoke test failed: {row.get('id')}")

    return sanitize({"valid": not errors, "errors": errors, "result": payload, "project_root": str(project_root)})


def _evaluate_response(spec: Mapping[str, Any], status_code: int, payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_status = spec.get("expected_status_code")
    if status_code != expected_status:
        errors.append(f"expected status {expected_status}, got {status_code}")
    expected_contract = spec.get("expected_contract")
    if expected_contract is not None and payload.get("contract") != expected_contract:
        errors.append(f"expected contract {expected_contract}, got {payload.get('contract')}")
    expected_field = spec.get("expected_payload_field")
    if expected_field is not None:
        observed = payload.get(expected_field)
        if observed != spec.get("expected_payload_value"):
            errors.append(f"expected payload.{expected_field}={spec.get('expected_payload_value')}, got {observed}")
    return errors
