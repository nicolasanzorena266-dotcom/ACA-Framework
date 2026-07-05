from __future__ import annotations

from aca_os.hosting_target_contract import (
    HOSTING_TARGET_CONTRACT,
    build_hosting_target_contract,
    validate_hosting_target_contract,
)
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_build_hosting_target_contract_is_platform_neutral() -> None:
    contract = build_hosting_target_contract(public_base_url="https://aca.example.test", platform="render-web-service")

    assert contract["contract"] == HOSTING_TARGET_CONTRACT
    assert contract["app"]["surface"] == "ACA Studio"
    assert contract["app"]["platform"] == "render-web-service"
    assert contract["runtime"]["external_ai_required"] is False
    assert contract["runtime"]["business_logic_location"] == "runtime"
    assert contract["process"]["startup_command"] == "python tools/aca_web.py --host 0.0.0.0"
    assert contract["public_routes"]["studio"] == "https://aca.example.test/studio"


def test_validate_hosting_target_contract_accepts_project_files() -> None:
    result = validate_hosting_target_contract(project_root=".")

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["contract"]["healthcheck"]["path"] == "/health"


def test_validate_hosting_target_contract_rejects_business_logic_in_adapter() -> None:
    contract = build_hosting_target_contract()
    contract["runtime"]["business_logic_location"] = "hosting_adapter"

    result = validate_hosting_target_contract(project_root=".", contract=contract)

    assert result["valid"] is False
    assert "hosting target must keep business logic in runtime" in result["errors"]


def test_runtime_endpoint_api_exposes_hosting_target_contract() -> None:
    api = RuntimeEndpointAPI()

    payload = api.hosting_target_contract(public_base_url="https://aca.example.test")
    validation = api.validate_hosting_target_contract(project_root=".")
    catalog_paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert payload["contract"] == HOSTING_TARGET_CONTRACT
    assert validation["valid"] is True
    assert "/hosting/target" in catalog_paths
    assert "/hosting/target/validate" in catalog_paths


def test_runtime_rest_routes_hosting_target_contract() -> None:
    rest = RuntimeRESTAPI()

    response = rest.route("GET", "/hosting/target", query={"public_base_url": "https://aca.example.test"})
    validation = rest.route("GET", "/hosting/target/validate")

    assert response.status_code == 200
    assert response.payload["contract"] == HOSTING_TARGET_CONTRACT
    assert response.payload["public_routes"]["health"] == "https://aca.example.test/health"
    assert validation.status_code == 200
    assert validation.payload["valid"] is True
