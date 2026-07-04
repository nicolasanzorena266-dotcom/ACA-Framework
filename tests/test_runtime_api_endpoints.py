from pathlib import Path

from aca_os.runtime_api_endpoints import RuntimeEndpointAPI


def test_runtime_endpoint_catalog_is_transport_neutral_and_complete():
    api = RuntimeEndpointAPI()

    catalog = api.catalog()
    paths = {endpoint["path"] for endpoint in catalog["endpoints"]}

    assert catalog["contract"] == "runtime_endpoints.v1"
    assert catalog["endpoint_count"] >= 15
    assert "/runtime/events" in paths
    assert "/runtime/components/{name}" in paths
    assert "/runtime/plugin-lifecycle" in paths
    assert all(endpoint["capability"] for endpoint in catalog["endpoints"])


def test_runtime_endpoint_component_detail_and_studio_view():
    api = RuntimeEndpointAPI()

    component = api.component("policy_manager")
    studio = api.studio()

    assert component["component"]["name"] == "policy_manager"
    assert "policy.evaluate" in component["component"]["capabilities"]
    assert studio["status"] == "ready"
    assert next(panel for panel in studio["panels"] if panel["id"] == "runtime_health")["data"]["component_count"] >= 10


def test_runtime_endpoint_generic_event_processing_returns_trace():
    api = RuntimeEndpointAPI()

    result = api.process_event(
        event_type="user_message",
        payload="Que es CLEAS?",
        metadata={"conversation_id": "endpoint-event"},
        include_trace=True,
        include_introspection=True,
    )

    assert result["conversation_id"] == "endpoint-event"
    assert result["policy_result"]["decision"] == "USE_TOOL"
    assert result["execution_trace"]["conversation_id"] == "endpoint-event"
    assert result["introspection"]["status"] == "ready"


def test_runtime_endpoint_plugin_load_lifecycle_transition_and_snapshot():
    api = RuntimeEndpointAPI()

    loaded = api.load_plugins(root="examples/plugins")
    lifecycle = api.plugin_lifecycle(root="examples/plugins")
    transitioned = api.transition_plugin(
        root="examples/plugins",
        plugin_name="example.echo_tool",
        action="initialize",
    )

    assert loaded["plugin_count"] == 3
    assert lifecycle["plugin_count"] == 3
    assert transitioned["plugin"]["plugin_name"] == "example.echo_tool"
    assert transitioned["plugin"]["state"] == "initialized"
    assert transitioned["lifecycle"]["states"]["initialized"] == 1


def test_runtime_endpoint_save_and_replay_session(tmp_path: Path):
    api = RuntimeEndpointAPI()
    path = tmp_path / "endpoint-session.aca.json"

    saved = api.save_session(message="Que es CLEAS?", conversation_id="endpoint-session", path=path)
    replayed = api.replay_session(path=path)

    assert saved["status"] == "written"
    assert saved["path"] == str(path)
    assert replayed["conversation_id"] == "endpoint-session"
    assert replayed["response"]
