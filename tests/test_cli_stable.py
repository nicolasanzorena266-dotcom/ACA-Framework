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
