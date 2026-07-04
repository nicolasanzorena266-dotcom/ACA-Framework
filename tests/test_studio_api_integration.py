from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI
from aca_os.studio_api import StudioAPIClient, build_studio_bootstrap


def test_studio_bootstrap_is_api_wiring_not_runtime_logic():
    api = RuntimeEndpointAPI()

    bootstrap = api.studio_bootstrap(base_url="http://127.0.0.1:8765")

    assert bootstrap["contract"] == "studio_api_integration.v1"
    assert bootstrap["base_url"] == "http://127.0.0.1:8765"
    assert bootstrap["read_only"] is True
    assert bootstrap["metadata"]["business_logic"] == "runtime_only"
    assert any(resource["path"] == "/studio/state" for resource in bootstrap["resources"])
    assert bootstrap["initial_view"]["metadata"]["contract"] == "studio_view.v1"


def test_studio_state_is_assembled_through_runtime_api_contracts():
    api = RuntimeEndpointAPI()

    state = api.studio_state()

    assert state["contract"] == "studio_api_state.v1"
    assert state["metadata"]["source"] == "runtime_rest_api"
    assert state["status"]["status"] == "ready"
    assert state["studio"]["title"] == "ACA Studio MVP"
    assert state["metrics"]["trace_count"] == 0
    assert state["components"]["component_count"] >= 11
    assert "plugins" in state


def test_studio_run_uses_runtime_events_endpoint_shape():
    api = RuntimeEndpointAPI()

    output = api.studio_run(message="Que es CLEAS?", conversation_id="studio-test")

    assert output["conversation_id"] == "studio-test"
    assert output["execution_trace"]["conversation_id"] == "studio-test"
    assert output["studio"]["metadata"]["source"] == "runtime_introspection_api"
    assert output["introspection"]["status"] == "ready"


def test_studio_api_client_consumes_rest_adapter_only():
    rest = RuntimeRESTAPI()
    client = StudioAPIClient(requester=rest.route, base_url="/api")

    bootstrap = client.bootstrap()
    state = client.read_state()
    output = client.run_message(message="Necesito hablar con un asesor")

    assert bootstrap["contract"] == "studio_api_integration.v1"
    assert state["contract"] == "studio_api_state.v1"
    assert output["conversation_id"] == "studio"
    assert output["studio"]["title"] == "ACA Studio MVP"


def test_rest_exposes_studio_api_routes():
    rest = RuntimeRESTAPI()

    bootstrap = rest.route("GET", "/studio/bootstrap", query={"base_url": "/aca"})
    state = rest.route("GET", "/studio/state")
    output = rest.route("POST", "/studio/run", body={"message": "Que es la franquicia?", "conversation_id": "rest-studio"})
    bad = rest.route("POST", "/studio/run", body={})

    assert bootstrap.status_code == 200
    assert bootstrap.payload["base_url"] == "/aca"
    assert state.payload["contract"] == "studio_api_state.v1"
    assert output.payload["conversation_id"] == "rest-studio"
    assert bad.status_code == 400
    assert bad.payload["error"]["code"] == "bad_request"


def test_build_studio_bootstrap_sanitizes_payloads():
    bootstrap = build_studio_bootstrap(
        runtime_health={"runtime_id": "r1", "runtime_status": "ready"},
        studio_view={"runtime_id": "r1", "panels": [{"callable": lambda: None}]},
    )

    assert bootstrap["runtime_id"] == "r1"
    assert bootstrap["initial_view"]["panels"][0]["callable"] == "<max-depth>"
