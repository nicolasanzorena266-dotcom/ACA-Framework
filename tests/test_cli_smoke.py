import json
import subprocess
import sys
from pathlib import Path


def test_cli_processes_message():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "aca_cli.py"),
            "--message",
            "Que es CLEAS?",
            "--conversation-id",
            "cli-test",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    data = json.loads(result.stdout)

    assert data["conversation_id"] == "cli-test"
    assert data["policy_result"]["decision"] == "USE_TOOL"
    assert "cleas" in data["tool_evidence"]