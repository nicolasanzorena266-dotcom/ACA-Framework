from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 compatibility
    import tomli as tomllib  # type: ignore


REQUIRED_PROJECT_PATHS = [
    "aca_os/runtime.py",
    "kernel/aca_kernel/core/kernel.py",
    "sdk/factory.py",
    "tools/aca_cli.py",
    "zero_cost/intent_matcher.py",
    "zero_cost/action_planner.py",
    "zero_cost/flow_router.py",
    "zero_cost/execution_plan.py",
]

RUNTIME_PIPELINE = [
    "conversation_manager",
    "intent_matcher",
    "action_planner",
    "flow_router",
    "execution_plan",
    "mission_manager",
    "policy_manager",
    "tool_engine",
    "compiler",
    "kernel",
    "memory_engine",
    "context_manager",
    "output",
]


@dataclass(frozen=True)
class ProjectVersion:
    name: str
    version: str
    milestone: str
    sprint: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "milestone": self.milestone,
            "sprint": self.sprint,
        }


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class DoctorReport:
    ok: bool
    root: str
    checks: List[DoctorCheck] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "root": self.root,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class RuntimeInspection:
    pipeline: List[str]
    zero_cost_components: List[str]
    status: str = "ready"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "pipeline": list(self.pipeline),
            "zero_cost_components": list(self.zero_cost_components),
        }


def project_root_from(start: str | Path | None = None) -> Path:
    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if (candidate / "pyproject.toml").exists() and (candidate / "aca_os").exists():
            return candidate

    raise FileNotFoundError("Could not locate ACA project root.")


def read_project_version(root: str | Path | None = None) -> ProjectVersion:
    project_root = project_root_from(root)
    pyproject = project_root / "pyproject.toml"
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)

    project = data.get("project", {})
    sprint = latest_sprint(project_root)
    return ProjectVersion(
        name=str(project.get("name", "aca-framework")),
        version=str(project.get("version", "unknown")),
        milestone="M1 Zero-Cost Runtime",
        sprint=sprint,
    )


def latest_sprint(root: str | Path | None = None) -> int:
    project_root = project_root_from(root)
    docs = project_root / "docs"
    values: List[int] = []
    for path in docs.glob("SPRINT_*.md"):
        stem = path.stem.replace("SPRINT_", "")
        if stem.isdigit():
            values.append(int(stem))
    return max(values) if values else 0


def run_doctor(root: str | Path | None = None) -> DoctorReport:
    project_root = project_root_from(root)
    checks: List[DoctorCheck] = []

    for relative in REQUIRED_PROJECT_PATHS:
        path = project_root / relative
        checks.append(
            DoctorCheck(
                name=f"path:{relative}",
                passed=path.exists(),
                detail="found" if path.exists() else "missing",
            )
        )

    version = read_project_version(project_root)
    checks.append(
        DoctorCheck(
            name="version",
            passed=version.version != "unknown" and version.sprint >= 24,
            detail=f"{version.name} {version.version} sprint {version.sprint}",
        )
    )

    return DoctorReport(
        ok=all(check.passed for check in checks),
        root=str(project_root),
        checks=checks,
    )


def inspect_runtime() -> RuntimeInspection:
    return RuntimeInspection(
        pipeline=RUNTIME_PIPELINE,
        zero_cost_components=[
            "IntentMatcher",
            "ActionPlanner",
            "FlowRouter",
            "ExecutionPlan",
        ],
    )


def run_pytest(root: str | Path | None = None) -> int:
    project_root = project_root_from(root)
    completed = subprocess.run(
        [sys.executable, "-m", "pytest"],
        cwd=project_root,
    )
    return int(completed.returncode)


def print_json(value: Dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))
