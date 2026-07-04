import json
import subprocess
import sys
from pathlib import Path


def test_cli_studio_outputs_json_view():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "aca_cli.py"),
            "studio",
            "--message",
            "Que es CLEAS?",
            "--format",
            "json",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    data = json.loads(result.stdout)
    assert data["title"] == "ACA Studio MVP"
    assert [panel["id"] for panel in data["panels"]][:3] == ["session", "runtime_health", "decision_graph"]


def test_cli_studio_writes_html_file(tmp_path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "studio.html"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools" / "aca_cli.py"),
            "studio",
            "--message",
            "Que es CLEAS?",
            "--format",
            "html",
            "--output",
            str(output),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    status = json.loads(result.stdout)
    assert status["status"] == "written"
    html = output.read_text(encoding="utf-8")
    assert "ACA Studio MVP" in html
    assert "Runtime Health" in html
