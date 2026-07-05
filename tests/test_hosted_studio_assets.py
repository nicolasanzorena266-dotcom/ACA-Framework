from __future__ import annotations

from pathlib import Path

from aca_os.hosted_runtime_healthcheck import build_hosted_runtime_healthcheck
from aca_os.hosted_studio_assets import (
    HOSTED_STUDIO_ASSETS,
    build_hosted_studio_assets,
    validate_hosted_studio_assets,
)
from aca_os.hosting_target_contract import build_hosting_target_contract
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_build_hosted_studio_assets_exposes_hosting_strategy() -> None:
    payload = build_hosted_studio_assets(public_base_url="https://aca.example.test")

    assert payload["contract"] == HOSTED_STUDIO_ASSETS
    assert payload["status"] == "ok"
    assert payload["surface"] == "ACA Studio"
    assert payload["serving"]["business_logic_location"] == "runtime"
    assert payload["serving"]["external_ai_required"] is False
    assert payload["routes"]["studio"] == "/studio"
    assert payload["routes"]["asset_strategy"] == "/hosting/studio-assets"
    assert payload["public_routes"]["studio"] == "https://aca.example.test/studio"
    assert {asset["id"] for asset in payload["assets"]} >= {
        "studio_html",
        "domain_pack_root",
        "public_demo_config",
        "hosting_contract_config",
    }


def test_validate_hosted_studio_assets_rejects_missing_required_asset(tmp_path: Path) -> None:
    strategy = build_hosted_studio_assets(project_root=tmp_path)

    result = validate_hosted_studio_assets(project_root=tmp_path, strategy=strategy)

    assert result["valid"] is False
    assert "missing required asset: studio/index.html" in result["errors"]
    assert "Studio HTML asset must exist and identify ACA Studio" in result["errors"]


def test_runtime_endpoint_api_exposes_hosted_studio_assets() -> None:
    api = RuntimeEndpointAPI()

    payload = api.hosted_studio_assets(public_base_url="https://aca.example.test")
    validation = api.validate_hosted_studio_assets(project_root=".")
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert payload["contract"] == HOSTED_STUDIO_ASSETS
    assert validation["valid"] is True
    assert "/hosting/studio-assets" in paths
    assert "/hosting/studio-assets/validate" in paths


def test_runtime_rest_routes_hosted_studio_assets() -> None:
    rest = RuntimeRESTAPI()

    response = rest.route("GET", "/hosting/studio-assets", query={"public_base_url": "https://aca.example.test"})
    validation = rest.route("GET", "/hosting/studio-assets/validate")

    assert response.status_code == 200
    assert response.payload["contract"] == HOSTED_STUDIO_ASSETS
    assert response.payload["public_routes"]["studio"] == "https://aca.example.test/studio"
    assert validation.status_code == 200
    assert validation.payload["valid"] is True


def test_hosting_contract_and_healthcheck_include_asset_strategy() -> None:
    contract = build_hosting_target_contract()
    healthcheck = build_hosted_runtime_healthcheck()

    paths = {route["path"] for route in contract["routes"]}
    checks = {check["id"] for check in healthcheck["checks"]}

    assert "/hosting/studio-assets" in paths
    assert "/hosting/studio-assets/validate" in paths
    assert "aca_os/hosted_studio_assets.py" in contract["required_files"]
    assert "hosted_studio_assets" in checks
    assert healthcheck["summary"]["required_failures"] == 0
