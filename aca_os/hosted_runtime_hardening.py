from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping

from aca_os.execution_trace import sanitize


HOSTED_RUNTIME_HARDENING = "hosted_runtime_hardening.v1"
HOSTED_RUNTIME_ERROR = "hosted_runtime_error.v1"
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_REQUEST_ID = "aca-request"


@dataclass(frozen=True)
class HostedHeaderPolicy:
    """HTTP response headers expected from hosted Runtime surfaces."""

    mode: str = "hosted"
    cache_control: str = "no-store"
    content_type: str = "application/json; charset=utf-8"
    request_id_header: str = "x-aca-request-id"
    runtime_header: str = "x-aca-runtime"
    mode_header: str = "x-aca-hosting-mode"
    hardening_header: str = "x-aca-hardening"

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "mode": self.mode,
                "cache_control": self.cache_control,
                "content_type": self.content_type,
                "request_id_header": self.request_id_header,
                "runtime_header": self.runtime_header,
                "mode_header": self.mode_header,
                "hardening_header": self.hardening_header,
                "required_headers": [
                    "content-type",
                    "cache-control",
                    self.request_id_header,
                    self.runtime_header,
                    self.mode_header,
                    self.hardening_header,
                ],
            }
        )


@dataclass(frozen=True)
class HostedErrorPolicy:
    """Stable error shape for hosted Runtime failures."""

    contract: str = HOSTED_RUNTIME_ERROR
    include_path: bool = True
    include_request_id: bool = True
    include_retry_hint: bool = True
    expose_tracebacks: bool = False
    cold_start_status_codes: tuple[int, ...] = (502, 503, 504)

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "contract": self.contract,
                "include_path": self.include_path,
                "include_request_id": self.include_request_id,
                "include_retry_hint": self.include_retry_hint,
                "expose_tracebacks": self.expose_tracebacks,
                "cold_start_status_codes": list(self.cold_start_status_codes),
                "stable_shape": {
                    "error": {
                        "contract": self.contract,
                        "code": "string",
                        "message": "string",
                        "status_code": "integer",
                        "path": "string",
                        "request_id": "string",
                        "retryable": "boolean",
                        "hint": "string",
                    }
                },
            }
        )


@dataclass(frozen=True)
class HostedRuntimeHardening:
    """Runtime hosting hardening contract.

    This is not business logic. It documents and produces the outer HTTP/runtime
    safety envelope needed by public hosting adapters.
    """

    mode: str = "hosted"
    platform: str = "render-web-service"
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_body_bytes: int = 128_000
    header_policy: HostedHeaderPolicy = field(default_factory=HostedHeaderPolicy)
    error_policy: HostedErrorPolicy = field(default_factory=HostedErrorPolicy)

    def to_dict(self) -> Dict[str, Any]:
        return sanitize(
            {
                "contract": HOSTED_RUNTIME_HARDENING,
                "status": "ready",
                "mode": self.mode,
                "platform": self.platform,
                "runtime": {
                    "external_ai_required": False,
                    "deterministic": True,
                    "business_logic_location": "runtime",
                    "adapter_logic_location": "rest_or_hosted_adapter",
                },
                "timeouts": {
                    "request_timeout_seconds": self.timeout_seconds,
                    "healthcheck_timeout_seconds": 10,
                    "cold_start_timeout_seconds": 90,
                    "public_smoke_timeout_seconds": max(self.timeout_seconds, 30),
                },
                "limits": {
                    "max_body_bytes": self.max_body_bytes,
                    "allow_empty_json_body": True,
                    "external_network_required_by_runtime": False,
                },
                "headers": self.header_policy.to_dict(),
                "errors": self.error_policy.to_dict(),
                "hosted_routes": {
                    "health": "/health",
                    "studio": "/studio",
                    "runtime_status": "/runtime/status",
                    "hardening": "/hosting/hardening",
                    "hardening_validate": "/hosting/hardening/validate",
                },
                "render_notes": [
                    "free services may cold start after idle time",
                    "first request should be retried before treating a timeout as product failure",
                    "runtime must bind to 0.0.0.0 and use the PORT environment variable",
                ],
                "acceptance_criteria": [
                    "REST responses include hosted hardening headers",
                    "REST errors use a stable hosted error envelope",
                    "hardening config validates required project files",
                    "health and status routes remain deterministic",
                    "no domain or business logic is added to the hosting layer",
                ],
                "non_goals": [
                    "no external LLM dependency",
                    "no provider-specific API calls",
                    "no visual redesign",
                    "no runtime core rewrite",
                ],
                "metadata": {"sprint": 67, "epic": "Public Deployment Execution"},
            }
        )


def build_hosted_runtime_hardening(
    *,
    mode: str = "hosted",
    platform: str = "render-web-service",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_body_bytes: int = 128_000,
) -> Dict[str, Any]:
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero.")
    if max_body_bytes <= 0:
        raise ValueError("max_body_bytes must be greater than zero.")
    return HostedRuntimeHardening(
        mode=mode,
        platform=platform,
        timeout_seconds=timeout_seconds,
        max_body_bytes=max_body_bytes,
        header_policy=HostedHeaderPolicy(mode=mode),
    ).to_dict()


def build_hosted_response_headers(
    *,
    mode: str = "hosted",
    request_id: str | None = None,
    content_type: str = "application/json; charset=utf-8",
    extra_headers: Mapping[str, str] | None = None,
) -> Dict[str, str]:
    request_id = (request_id or DEFAULT_REQUEST_ID).strip() or DEFAULT_REQUEST_ID
    headers = {
        "content-type": content_type,
        "cache-control": "no-store",
        "x-aca-runtime": "deterministic",
        "x-aca-hosting-mode": mode or "hosted",
        "x-aca-hardening": HOSTED_RUNTIME_HARDENING,
        "x-aca-request-id": request_id,
    }
    headers.update({str(key).lower(): str(value) for key, value in dict(extra_headers or {}).items()})
    return headers


def build_hosted_error_payload(
    *,
    code: str,
    message: str,
    status_code: int,
    path: str = "/",
    request_id: str | None = None,
    retryable: bool | None = None,
) -> Dict[str, Any]:
    if not code:
        code = "hosted_runtime_error"
    if retryable is None:
        retryable = status_code in {408, 429, 502, 503, 504}
    return sanitize(
        {
            "error": {
                "contract": HOSTED_RUNTIME_ERROR,
                "code": code,
                "message": message or "Hosted Runtime request failed.",
                "status_code": int(status_code),
                "path": path or "/",
                "request_id": request_id or DEFAULT_REQUEST_ID,
                "retryable": bool(retryable),
                "hint": _hosted_error_hint(status_code, retryable=bool(retryable)),
            }
        }
    )


def validate_hosted_runtime_hardening(
    *,
    project_root: str | Path = ".",
    hardening: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    root = Path(project_root)
    payload = dict(hardening or build_hosted_runtime_hardening())
    errors: list[str] = []

    if payload.get("contract") != HOSTED_RUNTIME_HARDENING:
        errors.append("invalid hosted runtime hardening contract")
    if payload.get("runtime", {}).get("business_logic_location") != "runtime":
        errors.append("hardening must keep business logic in runtime")
    if payload.get("runtime", {}).get("external_ai_required") is not False:
        errors.append("hosted runtime hardening must not require external AI")
    if payload.get("timeouts", {}).get("request_timeout_seconds", 0) <= 0:
        errors.append("request timeout must be positive")
    if payload.get("limits", {}).get("max_body_bytes", 0) <= 0:
        errors.append("max body bytes must be positive")

    headers = payload.get("headers", {})
    required_headers = set(headers.get("required_headers") or [])
    for header in {"content-type", "cache-control", "x-aca-request-id", "x-aca-runtime", "x-aca-hosting-mode", "x-aca-hardening"}:
        if header not in required_headers:
            errors.append(f"missing required hosted header: {header}")

    for required in [
        "aca_os/runtime_rest.py",
        "aca_os/runtime_api_endpoints.py",
        "aca_os/hosted_runtime_healthcheck.py",
        "aca_os/hosted_studio_assets.py",
        "aca_os/public_url_smoke_test.py",
        "render.yaml",
        "pyproject.toml",
    ]:
        if not (root / required).exists():
            errors.append(f"missing required file: {required}")

    return sanitize(
        {
            "contract": "hosted_runtime_hardening_validation.v1",
            "valid": not errors,
            "status": "valid" if not errors else "invalid",
            "errors": errors,
            "checked_files": [
                "aca_os/runtime_rest.py",
                "aca_os/runtime_api_endpoints.py",
                "aca_os/hosted_runtime_healthcheck.py",
                "aca_os/hosted_studio_assets.py",
                "aca_os/public_url_smoke_test.py",
                "render.yaml",
                "pyproject.toml",
            ],
            "hardening": payload,
        }
    )


def _hosted_error_hint(status_code: int, *, retryable: bool) -> str:
    if status_code in {502, 503, 504}:
        return "Hosted service may be cold-starting or temporarily unavailable; retry once before treating it as product failure."
    if status_code == 404:
        return "Check the public route and deployment configuration."
    if status_code == 400:
        return "Check request body and query parameters."
    if retryable:
        return "Retry the request after a short delay."
    return "Inspect the hosted Runtime response and deployment smoke test report."
