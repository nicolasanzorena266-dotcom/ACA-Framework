from __future__ import annotations

from aca_os.hosted_runtime_healthcheck import (
    HOSTED_RUNTIME_HEALTHCHECK,
    build_hosted_runtime_healthcheck,
    validate_hosted_runtime_healthcheck,
)
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_build_hosted_runtime_healthcheck_is_host_friendly() -> None:
    payload = build_hosted_runtime_healthcheck(public_base_url="https://aca.example.test")

    assert payload["contract"] == HOSTED_RUNTIME_HEALTHCHECK
    assert payload["status"] == "ok"
    assert payload["runtime"]["external_ai_required"] is False
    assert payload["runtime"]["business_logic_location"] == "runtime"
    assert payload["hosting"]["healthcheck_path"] == "/hosting/healthcheck"
    assert payload["hosting"]["platform_healthcheck_path"] == "/health"
    assert payload["hosting"]["public_base_url"] == "https://aca.example.test"
    assert {check["id"] for check in payload["checks"]} >= {
        "hosting_target_contract",
        "public_demo_readiness",
        "studio_asset",
        "default_domain_pack",
        "route_contract",
        "port_configuration",
    }


def test_validate_hosted_runtime_healthcheck_rejects_failed_required_checks() -> None:
    payload = build_hosted_runtime_healthcheck()
    payload["checks"][0]["status"] = "failed"

    result = validate_hosted_runtime_healthcheck(healthcheck=payload)

    assert result["valid"] is False
    assert "required check failed: runtime_contract" in result["errors"]


def test_runtime_endpoint_api_exposes_hosted_healthcheck() -> None:
    api = RuntimeEndpointAPI()

    payload = api.hosted_runtime_healthcheck(public_base_url="https://aca.example.test")
    validation = api.validate_hosted_runtime_healthcheck(project_root=".")
    catalog_paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert payload["contract"] == HOSTED_RUNTIME_HEALTHCHECK
    assert payload["status"] == "ok"
    assert validation["valid"] is True
    assert "/hosting/healthcheck" in catalog_paths
    assert "/hosting/healthcheck/validate" in catalog_paths


def test_runtime_rest_routes_hosted_healthcheck() -> None:
    rest = RuntimeRESTAPI()

    response = rest.route("GET", "/hosting/healthcheck", query={"public_base_url": "https://aca.example.test"})
    validation = rest.route("GET", "/hosting/healthcheck/validate")

    assert response.status_code == 200
    assert response.payload["contract"] == HOSTED_RUNTIME_HEALTHCHECK
    assert response.payload["hosting"]["public_base_url"] == "https://aca.example.test"
    assert response.payload["summary"]["required_failures"] == 0
    assert validation.status_code == 200
    assert validation.payload["valid"] is True


def test_rest_health_catalog_includes_hosted_healthcheck_path() -> None:
    rest = RuntimeRESTAPI()

    response = rest.route("GET", "/health")
    paths = {endpoint["path"] for endpoint in response.payload["endpoints"]}

    assert "/hosting/healthcheck" in paths
