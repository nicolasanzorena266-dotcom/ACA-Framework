from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from aca_os.execution_trace import sanitize


PUBLIC_URL_SMOKE_TEST = "public_url_smoke_test.v1"
PUBLIC_URL_SMOKE_RESULT = "public_url_smoke_result.v1"

Transport = Callable[[str, str, Mapping[str, str], bytes | None, float], tuple[int, Mapping[str, str], Any]]


@dataclass(frozen=True)
class PublicURLCheck:
    """One network smoke check against an externally hosted ACA demo URL."""

    id: str
    method: str
    path: str
    purpose: str
    required: bool = True
    expected_status_code: int = 200
    expected_contract: str | None = None
    expected_payload_field: str | None = None
    expected_payload_value: Any | None = None
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
                "body": dict(self.body),
            }
        )


def default_public_url_checks() -> tuple[PublicURLCheck, ...]:
    return (
        PublicURLCheck(
            "public_health",
            "GET",
            "/health",
            "Hosted service responds to the platform health endpoint.",
            expected_payload_field="status",
            expected_payload_value="ok",
        ),
        PublicURLCheck(
            "public_runtime_status",
            "GET",
            "/runtime/status",
            "Hosted Runtime can instantiate and report ready status.",
            expected_payload_field="status",
            expected_payload_value="ready",
        ),
        PublicURLCheck(
            "public_studio_bootstrap",
            "GET",
            "/studio/bootstrap",
            "Hosted Studio bootstrap contract is reachable from the public service.",
            expected_contract="studio_api_integration.v1",
        ),
        PublicURLCheck(
            "public_studio_page",
            "GET",
            "/studio",
            "Hosted Studio page is served for a browser user.",
            expected_status_code=200,
        ),
        PublicURLCheck(
            "public_demo_manifest",
            "GET",
            "/public-demo/manifest",
            "Public demo manifest remains reachable after deployment.",
            expected_contract="public_web_demo_prep.v1",
        ),
        PublicURLCheck(
            "public_demo_flow",
            "POST",
            "/demo/domain-flow",
            "Hosted demo flow executes against the default Domain Pack without external AI.",
            expected_contract="demo_domain_runtime_flow.v1",
            body={
                "message": "Necesito revisar un caso de soporte",
                "conversation_id": "public-url-smoke-test",
                "root": "examples/domain_packs",
                "pack_name": "example.customer_support",
            },
        ),
    )


def build_public_url_smoke_test_plan(*, public_base_url: str) -> Dict[str, Any]:
    base_url = normalize_public_base_url(public_base_url)
    checks = default_public_url_checks()
    return sanitize(
        {
            "contract": PUBLIC_URL_SMOKE_TEST,
            "status": "ready",
            "public_base_url": base_url,
            "check_count": len(checks),
            "checks": [check.to_dict() for check in checks],
            "coverage": {
                "health": "/health",
                "runtime": "/runtime/status",
                "studio": "/studio and /studio/bootstrap",
                "public_demo": "/public-demo/manifest",
                "demo_flow": "/demo/domain-flow",
            },
            "cold_start_note": "Render free services can return slowly after idle time; retry once before treating timeout as a product failure.",
            "acceptance_criteria": [
                "public health endpoint returns ok",
                "public runtime status returns ready",
                "Studio bootstrap and Studio page are reachable",
                "public demo manifest is exposed",
                "demo Domain Pack flow runs through the hosted REST surface",
                "failures are reported with path, status and diagnostic detail",
            ],
            "non_goals": [
                "no deploy operation",
                "no provider API call",
                "no secrets",
                "no external AI dependency",
            ],
            "metadata": {"sprint": 66, "epic": "Public Deployment Execution"},
        }
    )


def run_public_url_smoke_test(
    *,
    public_base_url: str,
    timeout_seconds: float = 20.0,
    transport: Transport | None = None,
) -> Dict[str, Any]:
    base_url = normalize_public_base_url(public_base_url)
    plan = build_public_url_smoke_test_plan(public_base_url=base_url)
    runner = transport or urllib_transport
    rows: list[Dict[str, Any]] = []

    for check in default_public_url_checks():
        spec = check.to_dict()
        url = urljoin(base_url + "/", check.path.lstrip("/"))
        status_code: int | None = None
        payload: Any = None
        headers: Mapping[str, str] = {}
        transport_error: str | None = None

        try:
            encoded_body = None
            if check.method.upper() != "GET" and check.body:
                encoded_body = json.dumps(dict(check.body)).encode("utf-8")
            status_code, headers, payload = runner(
                check.method.upper(),
                url,
                {"content-type": "application/json", "accept": "application/json"},
                encoded_body,
                timeout_seconds,
            )
        except Exception as exc:  # pragma: no cover - exercised through fake transport tests
            transport_error = f"{type(exc).__name__}: {exc}"

        errors = _evaluate_public_response(spec, status_code, payload, transport_error)
        rows.append(
            sanitize(
                {
                    "id": check.id,
                    "method": check.method.upper(),
                    "path": check.path,
                    "url": url,
                    "required": check.required,
                    "passed": not errors,
                    "status_code": status_code,
                    "errors": errors,
                    "observed_contract": payload.get("contract") if isinstance(payload, Mapping) else None,
                    "observed_status": payload.get("status") if isinstance(payload, Mapping) else None,
                    "content_type": dict(headers).get("content-type") or dict(headers).get("Content-Type"),
                }
            )
        )

    required_failures = [row for row in rows if row["required"] and not row["passed"]]
    return sanitize(
        {
            "contract": PUBLIC_URL_SMOKE_RESULT,
            "valid": not required_failures,
            "status": "ok" if not required_failures else "failed",
            "public_base_url": base_url,
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


def validate_public_url_smoke_test_result(result: Mapping[str, Any]) -> Dict[str, Any]:
    payload = dict(result)
    errors: list[str] = []

    if payload.get("contract") != PUBLIC_URL_SMOKE_RESULT:
        errors.append("invalid public URL smoke test result contract")
    if payload.get("valid") is not True:
        errors.append("public URL smoke test has required failures")
    if not payload.get("public_base_url"):
        errors.append("public_base_url is required")
    for row in payload.get("results", []):
        if isinstance(row, Mapping) and row.get("required") is not False and row.get("passed") is not True:
            errors.append(f"required public URL smoke check failed: {row.get('id')}")

    return sanitize({"valid": not errors, "errors": errors, "result": payload})


def normalize_public_base_url(public_base_url: str) -> str:
    if not public_base_url:
        raise ValueError("public_base_url is required.")
    base_url = public_base_url.strip().rstrip("/")
    if not (base_url.startswith("https://") or base_url.startswith("http://")):
        raise ValueError("public_base_url must start with http:// or https://.")
    return base_url


def urllib_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
    timeout_seconds: float,
) -> tuple[int, Mapping[str, str], Any]:
    request = Request(url, data=body, headers=dict(headers), method=method.upper())
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - explicit user-supplied smoke test URL
            raw = response.read()
            return response.status, dict(response.headers), _decode_payload(raw, dict(response.headers))
    except HTTPError as exc:
        raw = exc.read()
        return exc.code, dict(exc.headers), _decode_payload(raw, dict(exc.headers))
    except URLError as exc:
        raise ConnectionError(str(exc.reason)) from exc


def _decode_payload(raw: bytes, headers: Mapping[str, str]) -> Any:
    text = raw.decode("utf-8", errors="replace")
    content_type = headers.get("content-type") or headers.get("Content-Type") or ""
    if "application/json" in content_type.lower() or text.strip().startswith(("{", "[")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
    return {"raw": text, "content_type": content_type}


def _evaluate_public_response(
    spec: Mapping[str, Any],
    status_code: int | None,
    payload: Any,
    transport_error: str | None,
) -> list[str]:
    errors: list[str] = []
    if transport_error:
        errors.append(transport_error)
        return errors
    if status_code is None:
        errors.append("no status code returned")
        return errors
    expected_status = spec.get("expected_status_code")
    if status_code != expected_status:
        errors.append(f"expected status {expected_status}, got {status_code}")
    if not isinstance(payload, Mapping):
        errors.append("payload is not a mapping")
        return errors
    expected_contract = spec.get("expected_contract")
    if expected_contract is not None and payload.get("contract") != expected_contract:
        errors.append(f"expected contract {expected_contract}, got {payload.get('contract')}")
    expected_field = spec.get("expected_payload_field")
    if expected_field is not None:
        observed = payload.get(expected_field)
        if observed != spec.get("expected_payload_value"):
            errors.append(f"expected payload.{expected_field}={spec.get('expected_payload_value')}, got {observed}")
    return errors
