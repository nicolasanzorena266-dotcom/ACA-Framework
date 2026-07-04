from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

from aca_os.component_registry import ComponentRegistry
from aca_os.plugin_manifest import PluginManifest

PLUGIN_VALIDATOR_CONTRACT = "plugin_validator.v1"
DEFAULT_RUNTIME_VERSION = "0.3.0"

_DEFAULT_ALLOWED_PERMISSIONS = frozenset(
    {
        "component.read",
        "context.read",
        "event.publish",
        "event.read",
        "memory.read",
        "memory.write",
        "metrics.read",
        "policy.read",
        "trace.read",
        "tool.execute",
    }
)
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DOTTED_PATH = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_NAME = re.compile(r"^[a-zA-Z0-9_.:-]+$")


class PluginValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class PluginValidationIssue:
    code: str
    message: str
    severity: PluginValidationSeverity = PluginValidationSeverity.ERROR
    field: str = ""

    def __post_init__(self) -> None:
        if not self.code or not self.code.strip():
            raise ValueError("Plugin validation issue code is required.")
        if not self.message or not self.message.strip():
            raise ValueError("Plugin validation issue message is required.")
        if not isinstance(self.severity, PluginValidationSeverity):
            object.__setattr__(self, "severity", PluginValidationSeverity(self.severity))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "field": self.field,
        }


@dataclass(frozen=True)
class PluginValidationReport:
    contract: str
    valid: bool
    manifest_path: str | None = None
    manifest: PluginManifest | None = None
    issues: tuple[PluginValidationIssue, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == PluginValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == PluginValidationSeverity.WARNING)

    def messages(self, *, severity: PluginValidationSeverity | str | None = None) -> tuple[str, ...]:
        selected = PluginValidationSeverity(severity) if severity is not None else None
        return tuple(
            issue.message for issue in self.issues if selected is None or issue.severity == selected
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "valid": self.valid,
            "manifest_path": self.manifest_path,
            "manifest": self.manifest.to_dict() if self.manifest else None,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "issues": [issue.to_dict() for issue in self.issues],
            "metadata": dict(self.metadata),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class PluginValidator:
    """Deterministic Plugin SDK contract validator.

    The validator owns policy-level checks that sit between manifest parsing and
    loading. It never imports plugin entrypoints; it only inspects metadata and
    the runtime-facing Component Registry boundary.
    """

    def __init__(
        self,
        *,
        runtime_version: str = DEFAULT_RUNTIME_VERSION,
        allowed_permissions: Iterable[str] | None = None,
        component_registry: ComponentRegistry | None = None,
    ) -> None:
        self.runtime_version = runtime_version
        self.allowed_permissions = frozenset(allowed_permissions or _DEFAULT_ALLOWED_PERMISSIONS)
        self.component_registry = component_registry

    def bind_registry(self, registry: ComponentRegistry) -> None:
        self.component_registry = registry

    def validate(
        self,
        source: str | Path | Mapping[str, Any] | PluginManifest,
        *,
        registry: ComponentRegistry | None = None,
    ) -> PluginValidationReport:
        manifest_path: str | None = None
        issues: list[PluginValidationIssue] = []
        manifest: PluginManifest | None = None

        try:
            if isinstance(source, PluginManifest):
                manifest = source
            elif isinstance(source, Mapping):
                manifest = PluginManifest.from_dict(source)
            else:
                path = Path(source)
                manifest_path = path.as_posix()
                manifest = PluginManifest.from_file(path)
        except Exception as exc:
            issues.append(
                PluginValidationIssue(
                    code="manifest.invalid",
                    field="manifest",
                    message=f"Invalid plugin manifest: {exc}",
                )
            )
            return PluginValidationReport(
                contract=PLUGIN_VALIDATOR_CONTRACT,
                valid=False,
                manifest_path=manifest_path,
                issues=tuple(issues),
                metadata=self._metadata(),
            )

        issues.extend(self._validate_manifest(manifest))
        issues.extend(self._validate_registry(manifest, registry or self.component_registry))
        valid = not any(issue.severity == PluginValidationSeverity.ERROR for issue in issues)
        return PluginValidationReport(
            contract=PLUGIN_VALIDATOR_CONTRACT,
            valid=valid,
            manifest_path=manifest_path,
            manifest=manifest,
            issues=tuple(issues),
            metadata=self._metadata(),
        )

    def validate_many(
        self,
        sources: Iterable[str | Path | Mapping[str, Any] | PluginManifest],
        *,
        registry: ComponentRegistry | None = None,
    ) -> tuple[PluginValidationReport, ...]:
        return tuple(self.validate(source, registry=registry) for source in sources)

    def export_report(
        self,
        source: str | Path | Mapping[str, Any] | PluginManifest,
        *,
        format: str = "dict",
        registry: ComponentRegistry | None = None,
    ) -> Dict[str, Any] | str:
        report = self.validate(source, registry=registry)
        if format == "dict":
            return report.to_dict()
        if format == "json":
            return report.to_json()
        raise ValueError(f"Unsupported plugin validator export format: {format}")

    def _validate_manifest(self, manifest: PluginManifest) -> tuple[PluginValidationIssue, ...]:
        issues: list[PluginValidationIssue] = []
        if not _NAME.match(manifest.name):
            issues.append(_error("manifest.name.invalid", "name", f"Plugin name is not safe: {manifest.name}"))
        if not _NAME.match(manifest.version):
            issues.append(
                _error("manifest.version.invalid", "version", f"Plugin version is not safe: {manifest.version}")
            )
        issues.extend(self._validate_runtime(manifest))
        issues.extend(self._validate_entrypoint(manifest))
        issues.extend(self._validate_permissions(manifest))
        issues.extend(self._validate_hooks(manifest))
        issues.extend(self._validate_capabilities(manifest))
        return tuple(issues)

    def _validate_runtime(self, manifest: PluginManifest) -> tuple[PluginValidationIssue, ...]:
        issues: list[PluginValidationIssue] = []
        runtime = _version_tuple(self.runtime_version)
        minimum = _version_tuple(manifest.runtime.min_version)
        maximum = _version_tuple(manifest.runtime.max_version) if manifest.runtime.max_version else None
        if runtime < minimum:
            issues.append(
                _error(
                    "runtime.version.too_low",
                    "runtime.min_version",
                    f"Plugin requires ACA Runtime >= {manifest.runtime.min_version}; current is {self.runtime_version}.",
                )
            )
        if maximum is not None and runtime > maximum:
            issues.append(
                _error(
                    "runtime.version.too_high",
                    "runtime.max_version",
                    f"Plugin supports ACA Runtime <= {manifest.runtime.max_version}; current is {self.runtime_version}.",
                )
            )
        return tuple(issues)

    def _validate_entrypoint(self, manifest: PluginManifest) -> tuple[PluginValidationIssue, ...]:
        entrypoint = manifest.entrypoint
        issues: list[PluginValidationIssue] = []
        if not _DOTTED_PATH.match(entrypoint.module):
            issues.append(
                _error(
                    "entrypoint.module.invalid",
                    "entrypoint.module",
                    f"Plugin entrypoint module is not a safe dotted path: {entrypoint.module}",
                )
            )
        if not _IDENTIFIER.match(entrypoint.factory):
            issues.append(
                _error(
                    "entrypoint.factory.invalid",
                    "entrypoint.factory",
                    f"Plugin entrypoint factory is not a safe identifier: {entrypoint.factory}",
                )
            )
        return tuple(issues)

    def _validate_permissions(self, manifest: PluginManifest) -> tuple[PluginValidationIssue, ...]:
        issues: list[PluginValidationIssue] = []
        for permission in manifest.permissions:
            if permission.name not in self.allowed_permissions:
                issues.append(
                    _error(
                        "permission.not_allowed",
                        "permissions",
                        f"Plugin permission is not allowed by this runtime: {permission.name}",
                    )
                )
            if not permission.reason.strip():
                issues.append(
                    _warning(
                        "permission.reason.missing",
                        "permissions",
                        f"Plugin permission has no reason: {permission.name}",
                    )
                )
        return tuple(issues)

    def _validate_hooks(self, manifest: PluginManifest) -> tuple[PluginValidationIssue, ...]:
        issues: list[PluginValidationIssue] = []
        for hook in manifest.hooks:
            module, _, callable_name = hook.target.partition(":")
            if not module or not callable_name:
                issues.append(
                    _error(
                        "hook.target.invalid",
                        "hooks",
                        f"Plugin hook target must use module:function syntax: {hook.target}",
                    )
                )
                continue
            if not _DOTTED_PATH.match(module) or not _IDENTIFIER.match(callable_name):
                issues.append(
                    _error(
                        "hook.target.unsafe",
                        "hooks",
                        f"Plugin hook target is not safe: {hook.target}",
                    )
                )
        return tuple(issues)

    def _validate_capabilities(self, manifest: PluginManifest) -> tuple[PluginValidationIssue, ...]:
        issues: list[PluginValidationIssue] = []
        for capability in manifest.capabilities:
            if not _NAME.match(capability.name):
                issues.append(
                    _error(
                        "capability.name.invalid",
                        "capabilities",
                        f"Plugin capability name is not safe: {capability.name}",
                    )
                )
            if not _NAME.match(capability.kind):
                issues.append(
                    _error(
                        "capability.kind.invalid",
                        "capabilities",
                        f"Plugin capability kind is not safe: {capability.kind}",
                    )
                )
        return tuple(issues)

    def _validate_registry(
        self,
        manifest: PluginManifest,
        registry: ComponentRegistry | None,
    ) -> tuple[PluginValidationIssue, ...]:
        if registry is None:
            return ()
        issues: list[PluginValidationIssue] = []
        if registry.get(manifest.name) is not None:
            issues.append(
                _error(
                    "plugin.already_registered",
                    "name",
                    f"Plugin is already registered: {manifest.name}",
                )
            )
        missing = [name for name in manifest.dependencies if registry.get(name) is None]
        if missing:
            issues.append(
                _error(
                    "dependency.missing",
                    "dependencies",
                    f"Plugin declares missing dependencies: {', '.join(missing)}",
                )
            )
        return tuple(issues)

    def _metadata(self) -> Dict[str, Any]:
        return {
            "runtime_version": self.runtime_version,
            "allowed_permissions": sorted(self.allowed_permissions),
        }


def _version_tuple(version: str | None) -> tuple[int, int, int]:
    if version is None:
        return (0, 0, 0)
    parts = re.findall(r"\d+", version)
    values = [int(part) for part in parts[:3]]
    while len(values) < 3:
        values.append(0)
    return tuple(values)  # type: ignore[return-value]


def _error(code: str, field: str, message: str) -> PluginValidationIssue:
    return PluginValidationIssue(code=code, field=field, message=message)


def _warning(code: str, field: str, message: str) -> PluginValidationIssue:
    return PluginValidationIssue(
        code=code,
        field=field,
        message=message,
        severity=PluginValidationSeverity.WARNING,
    )
