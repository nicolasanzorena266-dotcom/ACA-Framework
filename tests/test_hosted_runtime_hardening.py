from pathlib import Path

from aca_os.hosted_runtime_hardening import (
    HOSTED_RUNTIME_ERROR,
    HOSTED_RUNTIME_HARDENING,
    build_hosted_error_payload,
    build_hosted_response_headers,
    build_hosted_runtime_hardening,
    validate_hosted_runtime_hardening,
)
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def test_hosted_runtime_hardening_contract_is_deterministic_and_hosting_only():
    contract = build_hosted_runtime_hardening(platform="render-web-service")

    assert contract["contract"] == HOSTED_RUNTIME_HARDENING
    assert contract["status"] == "ready"
    assert contract["platform"] == "render-web-service"
    assert contract["runtime"]["external_ai_required"] is False
    assert contract["runtime"]["business_logic_location"] == "runtime"
    assert contract["timeouts"]["request_timeout_seconds"] == 30
    assert contract["limits"]["max_body_bytes"] == 128000
    assert "/hosting/hardening" in contract["hosted_routes"].values()
    assert "no runtime core rewrite" in contract["non_goals"]


def test_hosted_response_headers_are_public_hosting_safe():
    headers = build_hosted_response_headers(mode="hosted", request_id="req-123")

    assert headers["content-type"] == "application/json; charset=utf-8"
    assert headers["cache-control"] == "no-store"
    assert headers["x-aca-runtime"] == "deterministic"
    assert headers["x-aca-hosting-mode"] == "hosted"
    assert headers["x-aca-hardening"] == HOSTED_RUNTIME_HARDENING
    assert headers["x-aca-request-id"] == "req-123"


def test_hosted_error_payload_has_stable_shape_and_retry_hint():
    payload = build_hosted_error_payload(
        code="not_found",
        message="No REST endpoint for GET /missing.",
        status_code=404,
        path="/missing",
        request_id="req-404",
    )

    error = payload["error"]
    assert error["contract"] == HOSTED_RUNTIME_ERROR
    assert error["code"] == "not_found"
    assert error["status_code"] == 404
    assert error["path"] == "/missing"
    assert error["request_id"] == "req-404"
    assert error["retryable"] is False
    assert "route" in error["hint"].lower()


def test_hosted_runtime_hardening_validation_checks_required_files():
    validation = validate_hosted_runtime_hardening(project_root=Path("."))

    assert validation["contract"] == "hosted_runtime_hardening_validation.v1"
    assert validation["valid"] is True
    assert validation["status"] == "valid"
    assert "aca_os/runtime_rest.py" in validation["checked_files"]
    assert validation["errors"] == []


def test_runtime_endpoint_api_exposes_hosted_hardening():
    api = RuntimeEndpointAPI()

    payload = api.hosted_runtime_hardening(platform="render-web-service")
    validation = api.validate_hosted_runtime_hardening(project_root=".")
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert payload["contract"] == HOSTED_RUNTIME_HARDENING
    assert validation["valid"] is True
    assert "/hosting/hardening" in paths
    assert "/hosting/hardening/validate" in paths


def test_rest_api_exposes_hardening_and_uses_hardened_headers_and_errors():
    rest = RuntimeRESTAPI()

    hardening = rest.route("GET", "/hosting/hardening")
    validation = rest.route("GET", "/hosting/hardening/validate")
    missing = rest.route("GET", "/missing-hosted-route")

    assert hardening.status_code == 200
    assert hardening.payload["contract"] == HOSTED_RUNTIME_HARDENING
    assert hardening.headers["x-aca-hardening"] == HOSTED_RUNTIME_HARDENING
    assert validation.payload["valid"] is True
    assert missing.status_code == 404
    assert missing.payload["error"]["contract"] == HOSTED_RUNTIME_ERROR
    assert missing.headers["cache-control"] == "no-store"
