import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "tools" / "aca_cli.py"


def _run(*args: str):
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def test_cli_status_components_plugins_metrics_and_run_commands():
    status = json.loads(_run("status").stdout)
    components = json.loads(_run("components", "list").stdout)
    plugins = json.loads(_run("plugins", "list", "--root", "examples/plugins").stdout)
    metrics = json.loads(_run("metrics", "--message", "Que es CLEAS?").stdout)
    executed = json.loads(_run("run", "--message", "Que es CLEAS?", "--trace").stdout)

    assert status["status"] == "ready"
    assert components["component_count"] >= 10
    assert plugins["plugin_count"] == 3
    assert metrics["trace_count"] == 1
    assert executed["execution_trace"]["events"]


def test_cli_stable_session_replay_command(tmp_path: Path):
    session_path = tmp_path / "stable.aca.json"

    saved = json.loads(_run("session", "save", "--message", "Que es CLEAS?", "--output", str(session_path)).stdout)
    replayed = json.loads(_run("session", "replay", str(session_path)).stdout)

    assert saved["status"] == "written"
    assert replayed["response"]


def test_cli_operational_benchmark_command():
    result = json.loads(
        _run(
            "operational-benchmark",
            "--scenario",
            "OB-004",
            "--format",
            "json",
        ).stdout
    )

    assert result["contract"] == "operational_work_benchmark_result.v1"
    assert result["scenario_count"] == 1
    assert result["quality"]["correct_operation_selection_percentage"] == 100.0


def test_cli_operational_real_world_benchmark_command():
    result = json.loads(
        _run(
            "operational-real-world-benchmark",
            "--conversation",
            "RW-010",
            "--format",
            "json",
        ).stdout
    )

    assert result["contract"] == "operational_real_world_benchmark_result.v1"
    assert result["conversation_count"] == 1
    assert "multi_work_detection_percentage" in result["quality"]


def test_cli_operational_governance_benchmark_command():
    result = json.loads(
        _run(
            "operational-governance-benchmark",
            "--scenario",
            "GOV-004",
            "--format",
            "json",
        ).stdout
    )

    assert result["contract"] == "operational_governance_benchmark_result.v1"
    assert result["scenario_count"] == 1
    assert result["quality"]["governance_accuracy_percentage"] == 100.0


def test_cli_operational_audit_ledger_benchmark_command():
    result = json.loads(
        _run(
            "operational-audit-ledger-benchmark",
            "--scenario",
            "LEDGER-004",
            "--format",
            "json",
        ).stdout
    )

    assert result["contract"] == "operational_audit_ledger_benchmark_result.v1"
    assert result["scenario_count"] == 1
    assert result["quality"]["ledger_accuracy_percentage"] == 100.0


def test_cli_operational_dry_run_benchmark_command():
    result = json.loads(
        _run(
            "operational-dry-run-benchmark",
            "--scenario",
            "DRY-001",
            "--format",
            "json",
        ).stdout
    )

    assert result["contract"] == "operational_dry_run_benchmark_result.v1"
    assert result["scenario_count"] == 1
    assert result["quality"]["end_to_end_success_percentage"] == 100.0


def test_cli_operational_production_benchmark_command(tmp_path: Path):
    result = json.loads(
        _run(
            "operational-production-benchmark",
            "--scenario",
            "PROD-001",
            "--storage-root",
            str(tmp_path),
            "--format",
            "json",
        ).stdout
    )

    assert result["contract"] == "operational_production_benchmark_result.v1"
    assert result["scenario_count"] == 1
    assert result["quality"]["production_success_percentage"] == 100.0
