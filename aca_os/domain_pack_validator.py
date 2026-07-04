from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from aca_os.domain_pack_manifest import DomainPackManifest


DOMAIN_PACK_VALIDATOR_CONTRACT = "domain_pack_validator.v1"
SUPPORTED_DOMAIN_PACK_ASSET_FORMATS = frozenset(
    {"json", "json-dir", "yaml", "yml", "markdown", "md", "text", "txt", "csv"}
)


class DomainPackValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"


@dataclass(frozen=True)
class DomainPackValidationIssue:
    """One deterministic validation finding for a Domain Pack."""

    code: str
    message: str
    path: str = ""
    severity: str = "error"

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise ValueError("Domain Pack validation issue code is required.")
        if not self.message or not self.message.strip():
            raise ValueError("Domain Pack validation issue message is required.")
        if self.severity not in {"error", "warning"}:
            raise ValueError(f"Unsupported Domain Pack validation severity: {self.severity}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class DomainPackValidationResult:
    """Observable validation result for one Domain Pack manifest."""

    status: DomainPackValidationStatus
    manifest_path: str
    pack_root: str
    manifest: DomainPackManifest | None = None
    issues: tuple[DomainPackValidationIssue, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return self.status == DomainPackValidationStatus.VALID

    @property
    def errors(self) -> tuple[str, ...]:
        return tuple(issue.message for issue in self.issues if issue.severity == "error")

    @property
    def warnings(self) -> tuple[str, ...]:
        return tuple(issue.message for issue in self.issues if issue.severity == "warning")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "valid": self.valid,
            "manifest_path": self.manifest_path,
            "pack_root": self.pack_root,
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "issues": [issue.to_dict() for issue in self.issues],
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass(frozen=True)
class DomainPackValidatorSnapshot:
    contract: str
    validation_count: int
    valid_count: int
    invalid_count: int
    results: tuple[DomainPackValidationResult, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "validation_count": self.validation_count,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "results": [result.to_dict() for result in self.results],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class DomainPackValidator:
    """Deterministic Domain Pack validator.

    The validator checks manifest structure, runtime compatibility and asset
    boundaries without importing domain code. It is intentionally stricter than
    the parser but still side-effect free.
    """

    def __init__(
        self,
        *,
        runtime_version: str = "0.3.0",
        supported_asset_formats: Iterable[str] = SUPPORTED_DOMAIN_PACK_ASSET_FORMATS,
    ) -> None:
        if not runtime_version or not runtime_version.strip():
            raise ValueError("Domain Pack validator runtime_version is required.")
        self.runtime_version = runtime_version
        self.supported_asset_formats = frozenset(supported_asset_formats)
        self._results: list[DomainPackValidationResult] = []

    def validate_manifest_file(self, path: str | Path) -> DomainPackValidationResult:
        manifest_path = Path(path)
        pack_root = manifest_path.parent
        issues: list[DomainPackValidationIssue] = []
        manifest: DomainPackManifest | None = None

        try:
            manifest = DomainPackManifest.from_file(manifest_path)
        except Exception as exc:
            result = DomainPackValidationResult(
                status=DomainPackValidationStatus.INVALID,
                manifest_path=manifest_path.as_posix(),
                pack_root=pack_root.as_posix(),
                issues=(
                    DomainPackValidationIssue(
                        code="manifest.invalid",
                        message=str(exc),
                        path=manifest_path.as_posix(),
                    ),
                ),
                metadata=self._metadata(),
            )
            self._results.append(result)
            return result

        issues.extend(self._validate_runtime(manifest))
        issues.extend(self._validate_dependencies(manifest))
        issues.extend(self._validate_assets(manifest, pack_root))

        status = (
            DomainPackValidationStatus.INVALID
            if any(issue.severity == "error" for issue in issues)
            else DomainPackValidationStatus.VALID
        )
        result = DomainPackValidationResult(
            status=status,
            manifest_path=manifest_path.as_posix(),
            pack_root=pack_root.as_posix(),
            manifest=manifest,
            issues=tuple(issues),
            metadata=self._metadata(),
        )
        self._results.append(result)
        return result

    def validate_manifest(self, manifest: DomainPackManifest, *, pack_root: str | Path = ".") -> DomainPackValidationResult:
        root = Path(pack_root)
        issues: list[DomainPackValidationIssue] = []
        issues.extend(self._validate_runtime(manifest))
        issues.extend(self._validate_dependencies(manifest))
        issues.extend(self._validate_assets(manifest, root))
        status = (
            DomainPackValidationStatus.INVALID
            if any(issue.severity == "error" for issue in issues)
            else DomainPackValidationStatus.VALID
        )
        result = DomainPackValidationResult(
            status=status,
            manifest_path="",
            pack_root=root.as_posix(),
            manifest=manifest,
            issues=tuple(issues),
            metadata=self._metadata(),
        )
        self._results.append(result)
        return result

    def require_valid_file(self, path: str | Path) -> DomainPackValidationResult:
        result = self.validate_manifest_file(path)
        if not result.valid:
            raise ValueError("Domain Pack validation failed: " + "; ".join(result.errors))
        return result

    def results(self) -> tuple[DomainPackValidationResult, ...]:
        return tuple(self._results)

    def snapshot(self) -> DomainPackValidatorSnapshot:
        return self._build_snapshot(self._results)

    def export(self, *, format: str = "dict") -> Dict[str, Any] | str:
        snapshot = self.snapshot()
        if format == "dict":
            return snapshot.to_dict()
        if format == "json":
            return snapshot.to_json()
        raise ValueError(f"Unsupported Domain Pack validator export format: {format}")

    def _metadata(self) -> Dict[str, Any]:
        return {
            "validator_contract": DOMAIN_PACK_VALIDATOR_CONTRACT,
            "runtime_version": self.runtime_version,
            "domain_code_imported": False,
        }

    def _validate_runtime(self, manifest: DomainPackManifest) -> tuple[DomainPackValidationIssue, ...]:
        issues: list[DomainPackValidationIssue] = []
        if _compare_versions(self.runtime_version, manifest.runtime.min_version) < 0:
            issues.append(
                DomainPackValidationIssue(
                    code="runtime.too_old",
                    message=(
                        "Domain Pack requires ACA Runtime >= "
                        f"{manifest.runtime.min_version}; current runtime is {self.runtime_version}."
                    ),
                    path="runtime.min_version",
                )
            )
        if manifest.runtime.max_version and _compare_versions(self.runtime_version, manifest.runtime.max_version) > 0:
            issues.append(
                DomainPackValidationIssue(
                    code="runtime.too_new",
                    message=(
                        "Domain Pack supports ACA Runtime <= "
                        f"{manifest.runtime.max_version}; current runtime is {self.runtime_version}."
                    ),
                    path="runtime.max_version",
                )
            )
        return tuple(issues)

    def _validate_dependencies(self, manifest: DomainPackManifest) -> tuple[DomainPackValidationIssue, ...]:
        issues: list[DomainPackValidationIssue] = []
        seen: set[str] = set()
        for dependency in manifest.dependencies:
            if not dependency.strip():
                issues.append(
                    DomainPackValidationIssue(
                        code="dependency.blank",
                        message="Domain Pack dependency name cannot be blank.",
                        path="dependencies",
                    )
                )
            if dependency == manifest.name:
                issues.append(
                    DomainPackValidationIssue(
                        code="dependency.self",
                        message=f"Domain Pack cannot depend on itself: {manifest.name}.",
                        path="dependencies",
                    )
                )
            if dependency in seen:
                issues.append(
                    DomainPackValidationIssue(
                        code="dependency.duplicate",
                        message=f"Duplicate Domain Pack dependency: {dependency}.",
                        path="dependencies",
                    )
                )
            seen.add(dependency)
        return tuple(issues)

    def _validate_assets(self, manifest: DomainPackManifest, pack_root: Path) -> tuple[DomainPackValidationIssue, ...]:
        issues: list[DomainPackValidationIssue] = []
        for asset in manifest.assets:
            asset_path = pack_root / asset.path
            if asset.format not in self.supported_asset_formats:
                issues.append(
                    DomainPackValidationIssue(
                        code="asset.unsupported_format",
                        message=f"Unsupported Domain Pack asset format for {asset.name}: {asset.format}.",
                        path=f"assets.{asset.name}.format",
                    )
                )
            if asset.required and not asset_path.exists():
                issues.append(
                    DomainPackValidationIssue(
                        code="asset.missing_required",
                        message=f"Missing required Domain Pack asset: {asset.path}.",
                        path=asset.path,
                    )
                )
                continue
            if asset_path.exists() and asset.format == "json":
                issues.extend(self._validate_json_file(asset.name, asset_path))
        return tuple(issues)

    def _validate_json_file(self, asset_name: str, asset_path: Path) -> tuple[DomainPackValidationIssue, ...]:
        if not asset_path.is_file():
            return (
                DomainPackValidationIssue(
                    code="asset.json_not_file",
                    message=f"JSON Domain Pack asset must be a file: {asset_path.as_posix()}.",
                    path=asset_path.as_posix(),
                ),
            )
        try:
            json.loads(asset_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return (
                DomainPackValidationIssue(
                    code="asset.invalid_json",
                    message=f"Invalid JSON Domain Pack asset {asset_name}: {exc}.",
                    path=asset_path.as_posix(),
                ),
            )
        return tuple()

    def _build_snapshot(self, results: Iterable[DomainPackValidationResult]) -> DomainPackValidatorSnapshot:
        values = tuple(results)
        return DomainPackValidatorSnapshot(
            contract=DOMAIN_PACK_VALIDATOR_CONTRACT,
            validation_count=len(values),
            valid_count=sum(1 for item in values if item.status == DomainPackValidationStatus.VALID),
            invalid_count=sum(1 for item in values if item.status == DomainPackValidationStatus.INVALID),
            results=values,
        )


def _compare_versions(left: str, right: str) -> int:
    left_parts = _version_parts(left)
    right_parts = _version_parts(right)
    width = max(len(left_parts), len(right_parts))
    left_parts.extend([0] * (width - len(left_parts)))
    right_parts.extend([0] * (width - len(right_parts)))
    if left_parts < right_parts:
        return -1
    if left_parts > right_parts:
        return 1
    return 0


def _version_parts(value: str) -> list[int]:
    cleaned = value.strip().split("-", 1)[0]
    parts: list[int] = []
    for item in cleaned.split("."):
        digits = "".join(char for char in item if char.isdigit())
        parts.append(int(digits or "0"))
    return parts or [0]
