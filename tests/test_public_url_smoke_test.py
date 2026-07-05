from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from aca_os.public_url_smoke_test import (
    PUBLIC_URL_SMOKE_RESULT,
    PUBLIC_URL_SMOKE_TEST,
    build_public_url_smoke_test_plan,
    normalize_public_base_url,
    run_public_url_smoke_test,
    validate_public_url_smoke_test_result,
)


def _fake_transport(method, url, headers, body, timeout_seconds):
    if url.endswith("/health"):
        return 200, {"content-type": "application/json"}, {"status": "ok"}
    if url.endswith("/runtime/status"):
        return 200, {"content-type": "application/json"}, {"status": "ready"}
    if url.endswith("/studio/bootstrap"):
        return 200, {"content-type": "application/json"}, {"contract": "studio_api_integration.v1"}
    if url.endswith("/studio"):
        return 200, {"content-type": "text/html"}, {"raw": "<html>ACA Studio</html>"}
    if url.endswith("/public-demo/manifest"):
        return 200, {"content-type": "application/json"}, {"contract": "public_web_demo_prep.v1"}
    if url.endswith("/demo/domain-flow"):
        assert method == "POST"
        assert body is not None
        payload = json.loads(body.decode("utf-8"))
        assert payload["pack_name"] == "example.customer_support"
        return 200, {"content-type": "application/json"}, {"contract": "demo_domain_runtime_flow.v1"}
    raise AssertionError(f"Unexpected URL: {url}")


def test_public_url_smoke_plan_contract():
    plan = build_public_url_smoke_test_plan(public_base_url="https://aca.example.com/")
    assert plan["contract"] == PUBLIC_URL_SMOKE_TEST
    assert plan["public_base_url"] == "https://aca.example.com"
    assert plan["check_count"] == 6
    assert {check["path"] for check in plan["checks"]} >= {"/health", "/studio", "/demo/domain-flow"}


def test_public_url_smoke_runner_passes_with_fake_transport():
    result = run_public_url_smoke_test(public_base_url="https://aca.example.com", transport=_fake_transport)
    assert result["contract"] == PUBLIC_URL_SMOKE_RESULT
    assert result["valid"] is True
    assert result["summary"]["passed"] == result["summary"]["total"]
    validation = validate_public_url_smoke_test_result(result)
    assert validation["valid"] is True


def test_public_url_smoke_runner_reports_required_failures():
    def broken_transport(method, url, headers, body, timeout_seconds):
        return 503, {"content-type": "application/json"}, {"status": "starting"}

    result = run_public_url_smoke_test(public_base_url="https://aca.example.com", transport=broken_transport)
    assert result["valid"] is False
    assert result["summary"]["required_failures"] == result["summary"]["total"]
    validation = validate_public_url_smoke_test_result(result)
    assert validation["valid"] is False


def test_public_url_normalization_rejects_missing_scheme():
    try:
        normalize_public_base_url("aca.example.com")
    except ValueError as exc:
        assert "http" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError")


def test_public_url_smoke_cli_plan_outputs_json():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "tools/aca_smoke_url.py", "https://aca.example.com", "--plan"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["contract"] == PUBLIC_URL_SMOKE_TEST
    assert payload["public_base_url"] == "https://aca.example.com"
