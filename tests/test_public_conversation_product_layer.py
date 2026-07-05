from __future__ import annotations

from pathlib import Path

from aca_core import PluginManifest
from aca_os.public_conversation_product_layer import (
    CLIENT_TECHNICAL_FORBIDDEN,
    FALSE_OPERATIONAL_CLAIMS,
    PublicConversationProductLayer,
)
from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI


def _assert_clean_client_response(response: str) -> None:
    lowered = response.lower()
    assert all(term not in lowered for term in CLIENT_TECHNICAL_FORBIDDEN)
    assert all(term not in lowered for term in FALSE_OPERATIONAL_CLAIMS)


def test_public_actions_must_point_to_existing_or_blocked_namespaced_capabilities() -> None:
    for manifest_path in Path("plugins").glob("*/manifest.yaml"):
        manifest = PluginManifest.from_file(manifest_path)
        declared = set(manifest.handles) | set(manifest.blocked_capabilities)
        for action in manifest.public_actions:
            assert "." in action.capability
            assert action.capability in declared
            if not action.enabled:
                assert action.disabled_reason


def test_public_flow_executes_plugin_hooks_and_segments_developer_trace() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    result = layer.run(message="fue cristales", conversation_id="glass-1")

    assert result["active_plugin_id"] == "galicia.insurance"
    assert result["active_capability"] == "insurance.glass"
    assert result["hook_execution"] == {"semantic": True, "policy": True, "planner": True}
    _assert_clean_client_response(result["response"])

    events = result["developer_trace"]["events"]
    event_types = {event["event_type"] for event in events}
    assert {"plugin.semantic.executed", "plugin.policy.executed", "plugin.planner.executed"} <= event_types
    for event in events:
        assert event["conversation_id"] == "glass-1"
        assert event["request_id"] == result["request_id"]
        assert event["trace_id"]
        assert event["timestamp"]
        assert "payload" in event


def test_public_trace_is_not_developer_trace() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    result = layer.run(message="cristales", conversation_id="glass-public-trace")

    assert result["public_trace"]["trace_type"] == "public_trace.v1"
    assert result["developer_trace"] != result["public_trace"]
    assert "events" not in result["public_trace"]
    assert "payload" not in str(result["public_trace"]).lower()


def test_action_driven_request_uses_public_action_id_and_real_capability_contract() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    initial = layer.run(message="quiero hablar con una persona", conversation_id="handoff-1")
    actions = {action["id"]: action for action in initial["public_actions"]}

    assert actions["prepare_handoff"]["capability"] == "insurance.handoff.prepare"
    assert actions["prepare_handoff"]["enabled"] is True
    assert actions["real_claim_status_lookup"]["capability"] == "insurance.claim_status.lookup"
    assert actions["real_claim_status_lookup"]["enabled"] is False
    assert actions["real_claim_status_lookup"]["disabled_reason"]

    result = layer.run(message="", conversation_id="handoff-1", public_action_id="prepare_handoff")
    assert result["input_type"] == "action"
    assert result["public_action_id"] == "prepare_handoff"
    assert result["active_capability"] == "insurance.handoff.prepare"
    _assert_clean_client_response(result["response"])


def test_disabled_action_does_not_fake_real_system_access() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    result = layer.run(message="consultá mi expediente", conversation_id="blocked-action", public_action_id="real_claim_status_lookup")

    assert result["input_type"] == "action"
    assert result["active_capability"] == "insurance.claim_status.lookup"
    assert result["diagnostic_view"]["status"] == "action_disabled"
    _assert_clean_client_response(result["response"])
    assert "expediente" not in result["response"].lower()


def test_multi_turn_cristales_client_mode_stays_representative_facing() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    messages = [
        "cargué una denuncia desde la app pero sigo sin tener respuesta",
        "fue cristales",
        "ya tengo la documentación, te la comparto a vos?",
        "ya me dijiste eso",
        "se supone que actúes como si yo fuera el cliente",
        "cristales",
        "ya pasaron más de 48hs hábiles",
        "quiero hablar con una persona",
    ]
    responses = [layer.run(message=message, conversation_id="glass-multiturn")["response"] for message in messages]

    for response in responses:
        _assert_clean_client_response(response)
    assert "48 horas hábiles" in responses[-2]
    assert "resumen" in responses[-1].lower()
    assert "persona" in responses[-1].lower()


def test_rest_and_endpoint_api_expose_public_conversation_product_layer() -> None:
    api = RuntimeEndpointAPI()
    rest = RuntimeRESTAPI()
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert "/public-conversation/product-layer" in paths
    assert "/public-conversation/product-layer/run" in paths
    assert rest.route("GET", "/public-conversation/product-layer").status_code == 200
    response = rest.route("POST", "/public-conversation/product-layer/run", body={"message": "cristales", "conversation_id": "rest-glass"})
    assert response.status_code == 200
    assert response.payload["active_plugin_id"] == "galicia.insurance"


def test_studio_contains_sprint72b_product_layer_markers_and_readme_encoding_is_clean() -> None:
    html = Path("studio/index.html").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "Sprint 72B Product Layer" in html
    assert "Plugin Execution Bridge" in html
    assert "public_action_id" in html
    assert "publicActions" in html
    assert "â†“" not in readme
    assert "↓" in readme
