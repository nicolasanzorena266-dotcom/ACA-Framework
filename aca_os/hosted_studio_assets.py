from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from aca_os.execution_trace import sanitize


HOSTED_STUDIO_ASSETS = "hosted_studio_assets.v1"


@dataclass(frozen=True)
class HostedStudioAsset:
    """A file or directory required to serve ACA Studio in hosted mode."""

    id: str
    path: Path
    route: str | None
    mime_type: str | None
    required: bool = True
    cache_policy: str = "no-store"
    purpose: str = ""

    def to_dict(self, *, project_root: Path) -> Dict[str, Any]:
        absolute = project_root / self.path
        exists = absolute.exists()
        size_bytes = absolute.stat().st_size if absolute.is_file() else None
        return sanitize(
            {
                "id": self.id,
                "path": self.path.as_posix(),
                "route": self.route,
                "mime_type": self.mime_type,
                "required": self.required,
                "exists": exists,
                "kind": "directory" if absolute.is_dir() else "file",
                "size_bytes": size_bytes,
                "cache_policy": self.cache_policy,
                "purpose": self.purpose,
            }
        )


@dataclass(frozen=True)
class HostedStudioAssetStrategy:
    """Platform-neutral strategy for serving ACA Studio assets.

    This contract is deliberately about asset discovery and route shape only.
    Runtime behavior remains behind RuntimeEndpointAPI and REST adapters.
    """

    project_root: Path = Path(".")
    public_base_url: str = "https://aca-demo.example.com"
    studio_path: Path = Path("studio/index.html")
    fallback_route: str = "/studio"
    api_base_route: str = "/"
    assets: tuple[HostedStudioAsset, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        assets = self.assets or default_hosted_studio_assets(self.studio_path)
        asset_rows = [asset.to_dict(project_root=self.project_root) for asset in assets]
        missing_required = [asset["path"] for asset in asset_rows if asset["required"] and not asset["exists"]]
        studio_file = self.project_root / self.studio_path
        studio_html_valid = _studio_html_valid(studio_file)
        status = "ok" if not missing_required and studio_html_valid else "degraded"

        return sanitize(
            {
                "contract": HOSTED_STUDIO_ASSETS,
                "status": status,
                "surface": "ACA Studio",
                "public_base_url": self.public_base_url.rstrip("/"),
                "serving": {
                    "mode": "hosted-static-shell-with-runtime-api",
                    "studio_route": self.fallback_route,
                    "fallback_route": self.fallback_route,
                    "api_base_route": self.api_base_route,
                    "asset_strategy": "single_html_shell_with_runtime_endpoints",
                    "business_logic_location": "runtime",
                    "interface_logic_location": "studio_shell",
                    "external_ai_required": False,
                },
                "routes": {
                    "studio": self.fallback_route,
                    "asset_strategy": "/hosting/studio-assets",
                    "asset_validation": "/hosting/studio-assets/validate",
                    "runtime_status": "/runtime/status",
                    "studio_binding": "/studio/binding",
                    "demo_domain_flow": "/demo/domain-flow",
                },
                "public_routes": {
                    "studio": f"{self.public_base_url.rstrip('/')}{self.fallback_route}",
                    "asset_strategy": f"{self.public_base_url.rstrip('/')}/hosting/studio-assets",
                    "asset_validation": f"{self.public_base_url.rstrip('/')}/hosting/studio-assets/validate",
                },
                "assets": asset_rows,
                "validation_hints": {
                    "missing_required": missing_required,
                    "studio_html_valid": studio_html_valid,
                    "studio_title_required": "ACA Studio",
                    "fallback_required": self.fallback_route == "/studio",
                },
                "cache": {
                    "html": "no-store",
                    "runtime_api": "no-store",
                    "static_future_assets": "public, max-age=3600",
                },
                "failure_behavior": {
                    "missing_studio_html": "return explicit 404 asset_missing payload instead of blank page",
                    "missing_optional_asset": "continue with degraded asset strategy",
                    "runtime_api_failure": "show visible Runtime unavailable state in Studio",
                },
                "acceptance_criteria": [
                    "GET /studio serves the Studio shell",
                    "GET /hosting/studio-assets returns hosted_studio_assets.v1",
                    "GET /hosting/studio-assets/validate returns valid true when required assets exist",
                    "missing required assets produce explicit validation errors",
                    "Studio assets do not contain runtime business logic",
                ],
                "metadata": {"sprint": 62, "epic": "Hosted Demo Path"},
            }
        )


def default_hosted_studio_assets(studio_path: str | Path = "studio/index.html") -> tuple[HostedStudioAsset, ...]:
    return (
        HostedStudioAsset(
            "studio_html",
            Path(studio_path),
            "/studio",
            "text/html; charset=utf-8",
            True,
            "no-store",
            "ACA Studio HTML shell served by the web adapter.",
        ),
        HostedStudioAsset(
            "domain_pack_root",
            Path("examples/domain_packs"),
            None,
            None,
            True,
            "no-store",
            "Domain Pack examples used by the public demo flow.",
        ),
        HostedStudioAsset(
            "public_demo_config",
            Path("deploy/public-web-demo.json"),
            None,
            "application/json",
            True,
            "no-store",
            "Public demo deployment configuration.",
        ),
        HostedStudioAsset(
            "hosting_contract_config",
            Path("deploy/hosting-target-contract.json"),
            None,
            "application/json",
            True,
            "no-store",
            "Platform-neutral hosting target configuration.",
        ),
    )


def build_hosted_studio_assets(
    *,
    project_root: str | Path = ".",
    public_base_url: str = "https://aca-demo.example.com",
    studio_path: str | Path = "studio/index.html",
    fallback_route: str = "/studio",
    api_base_route: str = "/",
) -> Dict[str, Any]:
    if not public_base_url:
        raise ValueError("public_base_url is required.")
    if not studio_path:
        raise ValueError("studio_path is required.")
    if not fallback_route.startswith("/"):
        raise ValueError("fallback_route must start with /.")
    if not api_base_route.startswith("/"):
        raise ValueError("api_base_route must start with /.")

    return HostedStudioAssetStrategy(
        project_root=Path(project_root),
        public_base_url=public_base_url,
        studio_path=Path(studio_path),
        fallback_route=fallback_route,
        api_base_route=api_base_route,
        assets=default_hosted_studio_assets(studio_path),
    ).to_dict()


def validate_hosted_studio_assets(
    *,
    project_root: str | Path = ".",
    strategy: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    payload = dict(strategy or build_hosted_studio_assets(project_root=project_root))
    errors: list[str] = []

    if payload.get("contract") != HOSTED_STUDIO_ASSETS:
        errors.append("invalid hosted Studio asset contract")
    serving = payload.get("serving", {})
    if serving.get("business_logic_location") != "runtime":
        errors.append("Studio asset strategy must keep business logic in runtime")
    if serving.get("external_ai_required") is not False:
        errors.append("Studio asset strategy must not require external AI")
    if payload.get("routes", {}).get("studio") != "/studio":
        errors.append("Studio route must remain /studio")

    missing_required = payload.get("validation_hints", {}).get("missing_required") or []
    for missing in missing_required:
        errors.append(f"missing required asset: {missing}")
    if payload.get("validation_hints", {}).get("studio_html_valid") is not True:
        errors.append("Studio HTML asset must exist and identify ACA Studio")

    asset_ids = {asset.get("id") for asset in payload.get("assets", []) if isinstance(asset, Mapping)}
    for required_id in {"studio_html", "domain_pack_root", "public_demo_config", "hosting_contract_config"}:
        if required_id not in asset_ids:
            errors.append(f"missing asset declaration: {required_id}")

    return sanitize(
        {
            "valid": not errors,
            "errors": errors,
            "strategy": payload,
            "project_root": str(project_root),
        }
    )


def _studio_html_valid(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return "ACA Studio" in content and "<html" in content.lower()
