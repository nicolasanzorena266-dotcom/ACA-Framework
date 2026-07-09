import json
import threading
from urllib.request import Request, urlopen

from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI
from aca_os.studio_runtime_binding import (
    STUDIO_RUNTIME_BINDING_CONTRACT,
    STUDIO_RUNTIME_RUN_CONTRACT,
    build_studio_runtime_binding,
)
from tools.aca_web import build_server


def test_studio_runtime_binding_contract_shapes_runtime_api_payloads():
    api = RuntimeEndpointAPI()

    binding = api.studio_binding(root="examples/domain_packs")

    assert binding["contract"] == STUDIO_RUNTIME_BINDING_CONTRACT
    assert binding["runtime"]["status"] == "ready"
    assert binding["domain"]["pack_count"] >= 2
    assert "example.customer_support" in binding["domain"]["loaded_packs"]
    assert binding["metadata"]["business_logic"] == "runtime_only"
    assert binding["metadata"]["domain_logic_embedded"] is False


def test_studio_state_now_exposes_binding_and_domain_context():
    api = RuntimeEndpointAPI()

    state = api.studio_state()

    assert state["contract"] == "studio_api_state.v1"
    assert state["binding"]["contract"] == STUDIO_RUNTIME_BINDING_CONTRACT
    assert state["domain_packs"]["contract"] == "domain_pack_runtime.v1"
    assert "domain_context" in state


def test_studio_binding_run_returns_execution_plus_refreshed_binding():
    api = RuntimeEndpointAPI()

    result = api.studio_binding_run(message="Hola", conversation_id="binding-test", root="examples/domain_packs")

    assert result["contract"] == STUDIO_RUNTIME_RUN_CONTRACT
    assert result["conversation_id"] == "binding-test"
    assert result["trace"]["operation_count"] > 0
    assert result["binding"]["contract"] == STUDIO_RUNTIME_BINDING_CONTRACT
    assert result["binding"]["domain"]["pack_count"] >= 2


def test_rest_api_routes_studio_binding_endpoints():
    rest = RuntimeRESTAPI()

    response = rest.route("GET", "/studio/binding", query={"root": "examples/domain_packs"})
    assert response.status_code == 200
    assert response.payload["contract"] == STUDIO_RUNTIME_BINDING_CONTRACT
    assert response.payload["domain"]["pack_count"] >= 2

    run = rest.route("POST", "/studio/binding/run", body={"message": "Hola", "conversation_id": "rest-binding"})
    assert run.status_code == 200
    assert run.payload["contract"] == STUDIO_RUNTIME_RUN_CONTRACT
    assert run.payload["conversation_id"] == "rest-binding"


def test_web_runtime_serves_bound_studio_and_binding_api():
    server = build_server("127.0.0.1", 0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with urlopen(f"http://{host}:{port}/studio", timeout=5) as response:
            studio_html = response.read().decode("utf-8")

        with urlopen(f"http://{host}:{port}/studio/binding?root=examples/domain_packs", timeout=5) as response:
            binding = json.loads(response.read().decode("utf-8"))

        request = Request(
            f"http://{host}:{port}/studio/binding/run",
            data=json.dumps({"message": "Hola", "conversation_id": "web-binding"}).encode("utf-8"),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            executed = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "ACA Studio" in studio_html
    assert "Proceso y acciones" in studio_html
    assert binding["contract"] == STUDIO_RUNTIME_BINDING_CONTRACT
    assert binding["domain"]["pack_count"] >= 2
    assert executed["contract"] == STUDIO_RUNTIME_RUN_CONTRACT


def test_build_studio_runtime_binding_is_data_only_projection():
    binding = build_studio_runtime_binding(
        status={"status": "ready", "runtime_id": "r1", "component_count": 1, "plugin_count": 0, "trace_count": 0},
        metrics={"trace_count": 0},
        components={"components": []},
        plugins={"plugin_count": 0, "plugins": []},
        domain_packs={"pack_count": 0, "packs": []},
        domain_context={"packs": []},
        endpoints={"endpoint_count": 1},
        studio={"runtime_id": "r1"},
    )

    assert binding["contract"] == STUDIO_RUNTIME_BINDING_CONTRACT
    assert binding["metadata"]["domain_logic_embedded"] is False
