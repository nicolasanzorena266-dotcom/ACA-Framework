import json
import subprocess
import sys
import threading
from urllib.request import Request, urlopen

from aca_os.web_runtime_launcher import build_local_web_runtime_plan, render_launch_banner
from tools.aca_web import build_server


def test_local_web_runtime_plan_exposes_stable_urls_and_commands():
    plan = build_local_web_runtime_plan(host="127.0.0.1", port=8765)
    data = plan.to_dict()

    assert data["contract"] == "local_web_runtime_launcher.v1"
    assert data["endpoints"]["studio"] == "http://127.0.0.1:8765/studio"
    assert data["endpoints"]["health"] == "http://127.0.0.1:8765/health"
    assert data["endpoints"]["domain_packs"] == "http://127.0.0.1:8765/runtime/domain-packs"
    assert data["commands"]["start"] == "python tools/aca_web.py --host 127.0.0.1 --port 8765"
    assert "Ctrl+C" in data["commands"]["stop"]


def test_local_web_runtime_plan_rejects_invalid_port():
    try:
        build_local_web_runtime_plan(port=0)
    except ValueError as exc:
        assert "port" in str(exc)
    else:
        raise AssertionError("Expected invalid port to fail")


def test_launch_banner_is_human_readable():
    banner = render_launch_banner(build_local_web_runtime_plan(port=9123))

    assert "ACA Local Web Runtime" in banner
    assert "http://127.0.0.1:9123/studio" in banner
    assert "Ctrl+C" in banner


def test_web_runtime_server_serves_studio_and_runtime_api():
    server = build_server("127.0.0.1", 0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with urlopen(f"http://{host}:{port}/studio", timeout=5) as response:
            studio = response.read().decode("utf-8")
            content_type = response.headers["content-type"]

        with urlopen(f"http://{host}:{port}/health", timeout=5) as response:
            health = json.loads(response.read().decode("utf-8"))

        request = Request(
            f"http://{host}:{port}/studio/run",
            data=json.dumps({"message": "Que es CLEAS?", "conversation_id": "web-test"}).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            executed = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "text/html" in content_type
    assert "ACA Studio" in studio
    assert health["status"] == "ok"
    assert executed["conversation_id"] == "web-test"


def test_web_runtime_cli_print_plan():
    result = subprocess.run(
        [sys.executable, "tools/aca_web.py", "--host", "127.0.0.1", "--port", "9001", "--print-plan"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["contract"] == "local_web_runtime_launcher.v1"
    assert payload["endpoints"]["studio"] == "http://127.0.0.1:9001/studio"
