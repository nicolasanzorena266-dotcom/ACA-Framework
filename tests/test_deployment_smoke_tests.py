from __future__ import annotations

from pathlib import Path

from aca_os.deployment_smoke_tests import (
    DEPLOYMENT_SMOKE_RESULTS,
    DEPLOYMENT_SMOKE_TESTS,
    build_deployment_smoke_test_plan,
    run_deployment_smoke_tests,
    validate_deployment_smoke_tests,
)
from aca_os.hosted_runtime_healthcheck import build_hosted_runtime_healthcheck
from aca_os.hosting_target_contract import build_hosting_target_contract
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_build_deployment_smoke_test_plan_covers_hosted_demo_surface() -> None:
    plan = build_deployment_smoke_test_plan(public_base_url="https://aca.example.test")

    assert plan["contract"] == DEPLOYMENT_SMOKE_TESTS
    assert plan["status"] == "ready"
    assert plan["public_base_url"] == "https://aca.example.test"
    assert {test["path"] for test in plan["tests"]} >= {
        "/health",
        "/runtime/status",
        "/studio/bootstrap",
        "/studio/binding",
        "/hosting/target/validate",
        "/hosting/healthcheck/validate",
        "/hosting/studio-assets/validate",
        "/demo/domain-flow",
    }
    assert plan["coverage"]["assets"] == "/hosting/studio-assets/validate"


def test_run_deployment_smoke_tests_uses_rest_adapter_routes() -> None:
    result = run_deployment_smoke_tests()

    assert result["contract"] == DEPLOYMENT_SMOKE_RESULTS
    assert result["valid"] is True
    assert result["summary"]["required_failures"] == 0
    assert result["summary"]["total"] >= 8
    assert {row["id"] for row in result["results"]} >= {
        "platform_health",
        "runtime_status",
        "studio_bootstrap",
        "studio_binding",
        "hosting_target_validation",
        "hosted_runtime_healthcheck_validation",
        "hosted_studio_assets_validation",
        "demo_domain_flow",
    }


def test_validate_deployment_smoke_tests_rejects_failed_required_row() -> None:
    result = run_deployment_smoke_tests()
    result["valid"] = False
    result["results"][0]["passed"] = False
    result["results"][0]["errors"] = ["boom"]

    validation = validate_deployment_smoke_tests(result=result)

    assert validation["valid"] is False
    assert "deployment smoke tests have required failures" in validation["errors"]
    assert "required smoke test failed: platform_health" in validation["errors"]


def test_runtime_endpoint_api_exposes_deployment_smoke_tests() -> None:
    api = RuntimeEndpointAPI()

    plan = api.deployment_smoke_test_plan()
    result = api.run_deployment_smoke_tests()
    validation = api.validate_deployment_smoke_tests(project_root=".")
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert plan["contract"] == DEPLOYMENT_SMOKE_TESTS
    assert result["valid"] is True
    assert validation["valid"] is True
    assert "/deploy/smoke-tests" in paths
    assert "/deploy/smoke-tests/run" in paths
    assert "/deploy/smoke-tests/validate" in paths


def test_runtime_rest_routes_deployment_smoke_tests() -> None:
    rest = RuntimeRESTAPI()

    plan = rest.route("GET", "/deploy/smoke-tests", query={"public_base_url": "https://aca.example.test"})
    run = rest.route("POST", "/deploy/smoke-tests/run", body={"public_base_url": "https://aca.example.test"})
    validation = rest.route("GET", "/deploy/smoke-tests/validate")

    assert plan.status_code == 200
    assert plan.payload["contract"] == DEPLOYMENT_SMOKE_TESTS
    assert run.status_code == 200
    assert run.payload["contract"] == DEPLOYMENT_SMOKE_RESULTS
    assert run.payload["valid"] is True
    assert validation.status_code == 200
    assert validation.payload["valid"] is True


def test_hosting_contract_and_healthcheck_include_smoke_tests() -> None:
    contract = build_hosting_target_contract()
    healthcheck = build_hosted_runtime_healthcheck()

    paths = {route["path"] for route in contract["routes"]}
    checks = {check["id"] for check in healthcheck["checks"]}

    assert "/deploy/smoke-tests" in paths
    assert "/deploy/smoke-tests/run" in paths
    assert "/deploy/smoke-tests/validate" in paths
    assert "aca_os/deployment_smoke_tests.py" in contract["required_files"]
    assert "deployment_smoke_tests" in checks
    assert healthcheck["summary"]["required_failures"] == 0


def test_deployment_smoke_test_config_file_is_present() -> None:
    path = Path("deploy/deployment-smoke-tests.json")

    assert path.exists()
    assert DEPLOYMENT_SMOKE_TESTS in path.read_text(encoding="utf-8")
