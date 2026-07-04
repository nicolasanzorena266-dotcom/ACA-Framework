from aca_os.runtime_rest import RuntimeRESTAPI


def test_rest_exposes_runtime_endpoint_catalog_and_component_detail():
    api = RuntimeRESTAPI()

    health = api.route("GET", "/health").payload
    component = api.route("GET", "/runtime/components/policy_manager").payload

    assert health["contract"] == "runtime_endpoints.v1"
    assert health["adapter"] == "runtime-rest"
    assert any(endpoint["path"] == "/runtime/events" for endpoint in health["endpoints"])
    assert component["component"]["name"] == "policy_manager"


def test_rest_processes_generic_runtime_events():
    api = RuntimeRESTAPI()

    response = api.route(
        "POST",
        "/runtime/events",
        body={
            "event_type": "user_message",
            "payload": "Que es CLEAS?",
            "metadata": {"conversation_id": "rest-event"},
            "include_trace": True,
        },
    )

    assert response.status_code == 200
    assert response.payload["conversation_id"] == "rest-event"
    assert response.payload["execution_trace"]["conversation_id"] == "rest-event"


def test_rest_plugin_load_lifecycle_and_errors_are_stable():
    api = RuntimeRESTAPI()

    loaded = api.route("POST", "/runtime/plugins/load", body={"root": "examples/plugins"})
    lifecycle = api.route("GET", "/runtime/plugin-lifecycle", query={"root": "examples/plugins"})
    transitioned = api.route(
        "POST",
        "/runtime/plugin-lifecycle",
        body={"root": "examples/plugins", "plugin_name": "example.echo_tool", "action": "initialize"},
    )
    missing_component = api.route("GET", "/runtime/components/nope")

    assert loaded.payload["plugin_count"] == 3
    assert lifecycle.payload["plugin_count"] == 3
    assert transitioned.payload["plugin"]["state"] == "initialized"
    assert missing_component.status_code == 404
    assert missing_component.payload["error"]["code"] == "not_found"


def test_rest_saves_sessions_through_runtime_endpoint():
    api = RuntimeRESTAPI()

    missing = api.route("POST", "/sessions/save", body={})

    assert missing.status_code == 400
    assert missing.payload["error"]["code"] == "bad_request"
