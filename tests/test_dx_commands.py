import json
import subprocess
import sys
from pathlib import Path

from aca_os.dx import inspect_runtime, latest_sprint, read_project_version, run_doctor


def test_latest_sprint_detects_sprint_24():
    root = Path(__file__).resolve().parents[1]

    assert latest_sprint(root) >= 24


def test_doctor_report_passes_for_repo_root():
    root = Path(__file__).resolve().parents[1]

    report = run_doctor(root)

    assert report.ok is True
    assert any(check.name == "path:zero_cost/execution_plan.py" for check in report.checks)


def test_runtime_inspection_exposes_zero_cost_pipeline():
    inspection = inspect_runtime()

    assert inspection.status == "ready"
    assert inspection.pipeline[:5] == [
        "conversation_manager",
        "intent_matcher",
        "action_planner",
        "flow_router",
        "execution_plan",
    ]
    assert "ExecutionPlan" in inspection.zero_cost_components


def test_cli_version_command_outputs_json():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "aca_cli.py"), "version"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    data = json.loads(result.stdout)
    assert data["name"] == "aca-framework"
    assert data["sprint"] >= 24
    assert data["milestone"] == "M1 Zero-Cost Runtime"


def test_cli_inspect_runtime_command_outputs_pipeline():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "tools" / "aca_cli.py"), "inspect", "runtime"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    data = json.loads(result.stdout)
    assert data["status"] == "ready"
    assert "flow_router" in data["pipeline"]
