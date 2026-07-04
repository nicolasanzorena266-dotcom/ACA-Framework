import json
import subprocess
import sys
from pathlib import Path

from aca_kernel.core.events import Event
from sdk.factory import process_message


def test_process_message_exposes_execution_trace():
    result = process_message("Que es CLEAS?", conversation_id="trace-test")

    trace = result["execution_trace"]
    assert trace["conversation_id"] == "trace-test"
    assert "runtime.execution_plan_created" in trace["operations"]


def test_cli_trace_command_outputs_execution_trace_json():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "aca_cli.py"),
            "trace",
            "last",
            "--message",
            "Que es CLEAS?",
            "--conversation-id",
            "cli-trace",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    data = json.loads(result.stdout)
    assert data["conversation_id"] == "cli-trace"
    assert "INTENT_MATCH" in data["operations"]
    assert "runtime.process.completed" in data["operations"]
