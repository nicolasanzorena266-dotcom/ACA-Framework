import json
import threading
from urllib.request import Request, urlopen

from tools.aca_rest import build_server


def test_rest_server_serves_health_and_run_requests():
    server = build_server("127.0.0.1", 0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with urlopen(f"http://{host}:{port}/health", timeout=5) as response:
            health = json.loads(response.read().decode("utf-8"))

        request = Request(
            f"http://{host}:{port}/runtime/run",
            data=json.dumps({"message": "Que es CLEAS?", "conversation_id": "http-test"}).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            executed = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert health["status"] == "ok"
    assert executed["conversation_id"] == "http-test"
    assert executed["policy_result"]["decision"] == "USE_TOOL"
