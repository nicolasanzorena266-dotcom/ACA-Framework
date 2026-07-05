from __future__ import annotations

from pathlib import Path

from aca_os.first_public_hosted_demo import (
    FIRST_PUBLIC_HOSTED_DEMO,
    build_first_public_hosted_demo,
    validate_first_public_hosted_demo,
)
from aca_os.hosted_runtime_healthcheck import build_hosted_runtime_healthcheck
from aca_os.hosting_target_contract import build_hosting_target_contract
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_build_first_public_hosted_demo_contract_targets_public_link() -> None:
    demo = build_first_public_hosted_demo(public_base_url="https://aca.example.test")

    assert demo["contract"] == FIRST_PUBLIC_HOSTED_DEMO
    assert demo["status"] == "ready"
    assert demo["app"]["surface"] == "ACA Studio"
    assert demo["public_urls"]["studio"] == "https://aca.example.test/studio"
    assert demo["runtime"]["start_command"] == "python tools/aca_web.py --host 0.0.0.0"
    assert demo["runtime"]["external_ai_required"] is False
    assert "/hosted-demo/first" in demo["required_routes"]
    assert "/hosted-demo/first/validate" in demo["required_routes"]


def test_validate_first_public_hosted_demo_uses_project_artifacts() -> None:
    validation = validate_first_public_hosted_demo(project_root=".")

    assert validation["contract"] == "first_public_hosted_demo_validation.v1"
    assert validation["valid"] is True
    assert validation["errors"] == []
    assert validation["checks"] == {
        "hosting_target": True,
        "hosted_runtime_healthcheck": True,
        "hosted_studio_assets": True,
        "deployment_smoke_tests": True,
    }


def test_runtime_endpoint_api_exposes_first_public_hosted_demo() -> None:
    api = RuntimeEndpointAPI()

    demo = api.first_public_hosted_demo(public_base_url="https://aca.example.test")
    validation = api.validate_first_public_hosted_demo(project_root=".")
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert demo["contract"] == FIRST_PUBLIC_HOSTED_DEMO
    assert validation["valid"] is True
    assert "/hosted-demo/first" in paths
    assert "/hosted-demo/first/validate" in paths


def test_runtime_rest_routes_first_public_hosted_demo() -> None:
    rest = RuntimeRESTAPI()

    demo = rest.route("GET", "/hosted-demo/first", query={"public_base_url": "https://aca.example.test"})
    validation = rest.route("GET", "/hosted-demo/first/validate")

    assert demo.status_code == 200
    assert demo.payload["contract"] == FIRST_PUBLIC_HOSTED_DEMO
    assert demo.payload["public_urls"]["health"] == "https://aca.example.test/health"
    assert validation.status_code == 200
    assert validation.payload["valid"] is True


def test_hosting_contract_and_healthcheck_reference_first_public_demo() -> None:
    contract = build_hosting_target_contract(public_base_url="https://aca.example.test")
    healthcheck = build_hosted_runtime_healthcheck()

    routes = {route["path"] for route in contract["routes"]}
    checks = {check["id"] for check in healthcheck["checks"]}

    assert "/hosted-demo/first" in routes
    assert "/hosted-demo/first/validate" in routes
    assert "aca_os/first_public_hosted_demo.py" in contract["required_files"]
    assert "first_public_hosted_demo" in checks


def test_deployment_smoke_tests_include_first_public_demo_routes() -> None:
    rest = RuntimeRESTAPI()

    plan = rest.route("GET", "/deploy/smoke-tests")
    result = rest.route("POST", "/deploy/smoke-tests/run")

    paths = {test["path"] for test in plan.payload["tests"]}
    ids = {row["id"] for row in result.payload["results"]}

    assert "/hosted-demo/first" in paths
    assert "/hosted-demo/first/validate" in paths
    assert "first_public_hosted_demo" in ids
    assert "first_public_hosted_demo_validation" in ids
    assert result.payload["valid"] is True


def test_first_public_hosted_demo_config_file_is_present() -> None:
    path = Path("deploy/first-public-hosted-demo.json")

    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert FIRST_PUBLIC_HOSTED_DEMO in text
    assert "https://aca-public-web-demo.onrender.com/studio" in text
