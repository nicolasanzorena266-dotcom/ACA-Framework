import json
import subprocess
import sys
from pathlib import Path


def test_cli_inspect_session_outputs_introspection_snapshot():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "aca_cli.py"),
            "inspect",
            "session",
            "--message",
            "Que es CLEAS?",
            "--conversation-id",
            "cli-inspect",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    data = json.loads(result.stdout)
    assert data["status"] == "ready"
    assert data["last_state"]["conversation_id"] == "cli-inspect"
    assert data["metrics"]["trace_count"] == 1
    assert "runtime.process.completed" in data["event_bus"]["event_types"]


def test_cli_message_can_include_introspection_snapshot():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "aca_cli.py"),
            "--message",
            "Que es CLEAS?",
            "--conversation-id",
            "cli-message-inspect",
            "--introspection",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    data = json.loads(result.stdout)
    assert data["introspection"]["last_state"]["conversation_id"] == "cli-message-inspect"
    assert data["introspection"]["last_trace"]["event_count"] > 0
