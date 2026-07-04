import json
import subprocess
import sys
from pathlib import Path


def test_cli_session_save_show_replay_and_compare(tmp_path: Path):
    root = Path(__file__).resolve().parents[1]
    cli = root / "tools" / "aca_cli.py"
    left = tmp_path / "left.aca.json"
    right = tmp_path / "right.aca.json"

    subprocess.run(
        [sys.executable, str(cli), "session", "save", "--message", "Que es CLEAS?", "--output", str(left)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [sys.executable, str(cli), "session", "save", "--message", "Que es CLEAS?", "--output", str(right)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    shown = subprocess.run(
        [sys.executable, str(cli), "session", "show", str(left), "--summary"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    replayed = subprocess.run(
        [sys.executable, str(cli), "session", "replay", str(left)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    compared = subprocess.run(
        [sys.executable, str(cli), "session", "compare", str(left), str(right)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(shown.stdout)["trace_event_count"] > 0
    assert json.loads(replayed.stdout)["response"]
    assert json.loads(compared.stdout)["same_response"] is True
