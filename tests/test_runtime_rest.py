import json
from pathlib import Path

from aca_os.runtime_rest import RuntimeRESTAPI, RESTResponse


def test_rest_health_and_endpoint_catalog_are_stable():
    api = RuntimeRESTAPI()

    response = api.route("GET", "/health")

    assert isinstance(response, RESTResponse)
    assert response.status_code == 200
    assert response.payload["status"] == "ok"
    assert response.payload["adapter"] == "runtime-rest"
    assert {endpoint["path"] for endpoint in response.payload["endpoints"]} >= {
        "/health",
        "/runtime/status",
        "/runtime/run",
        "/runtime/trace",
        "/sessions/replay",
    }


def test_rest_runtime_status_components_plugins_and_metrics():
    api = RuntimeRESTAPI()

    status = api.route("GET", "/runtime/status").payload
    components = api.route("GET", "/runtime/components").payload
    plugins = api.route("GET", "/runtime/plugins", query={"root": "examples/plugins"}).payload
    metrics = api.route("GET", "/runtime/metrics").payload

    assert status["status"] == "ready"
    assert status["component_count"] >= 10
    assert components["component_count"] >= 10
    assert plugins["plugin_count"] == 3
    assert metrics["trace_count"] == 0


def test_rest_run_is_transport_only_and_can_include_runtime_views():
    api = RuntimeRESTAPI()

    response = api.route(
        "POST",
        "/runtime/run",
        body={
            "message": "Que es CLEAS?",
            "conversation_id": "rest-test",
            "include_events": True,
            "include_trace": True,
            "include_introspection": True,
            "include_studio": True,
        },
    )

    assert response.status_code == 200
    assert response.payload["conversation_id"] == "rest-test"
    assert response.payload["policy_result"]["decision"] == "USE_TOOL"
    assert response.payload["execution_trace"]["events"]
    assert response.payload["runtime_events"]
    assert response.payload["introspection"]["status"] == "ready"
    assert response.payload["studio"]["status"] == "ready"


def test_rest_trace_and_introspection_endpoints():
    api = RuntimeRESTAPI()

    trace = api.route(
        "POST",
        "/runtime/trace",
        body=json.dumps({"message": "Que es CLEAS?", "conversation_id": "rest-trace"}),
    ).payload
    introspection = api.route("GET", "/runtime/introspection").payload

    assert trace["conversation_id"] == "rest-trace"
    assert trace["events"]
    assert introspection["status"] == "ready"


def test_rest_session_replay_roundtrip(tmp_path: Path):
    api = RuntimeRESTAPI()
    session_path = tmp_path / "rest-session.aca.json"

    saved = api.route(
        "POST",
        "/runtime/run",
        body={
            "message": "Que es CLEAS?",
            "conversation_id": "rest-session",
            "save_session_path": str(session_path),
        },
    ).payload
    replayed = api.route("POST", "/sessions/replay", body={"path": str(session_path)}).payload

    assert saved["session_path"] == str(session_path)
    assert replayed["response"]


def test_rest_errors_are_predictable():
    api = RuntimeRESTAPI()

    missing = api.route("GET", "/nope")
    bad_json = api.route("POST", "/runtime/run", body="{no")
    missing_message = api.route("POST", "/runtime/run", body={})

    assert missing.status_code == 404
    assert missing.payload["error"]["code"] == "not_found"
    assert bad_json.status_code == 400
    assert missing_message.status_code == 400
