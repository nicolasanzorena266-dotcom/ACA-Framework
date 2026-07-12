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


def _assert_runtime_pipeline(result: dict) -> None:
    assert result["public_trace"]["source"] == "ACAOSRuntime"
    assert result["diagnostic_view"]["source"] == "ACAOSRuntime"
    assert result["diagnostic_view"]["runtime_execution_engine"]["official_engine"] == "runtime_executor"
    assert result["diagnostic_view"]["conversation_state_runtime"]["operational_owner"] == "conversation_manager"
    assert "narrative_response_composer" in result["diagnostic_view"]
    assert "conversation_response_plan" in result["public_trace"]["contracts_used"]
    assert result["cognitive_turn"]["source"] == "ACAOSRuntime"
    assert result["conversation_memory"]["source"] == "runtime_conversation_state_projection"
    assert result["runtime_response"] == result["response"]
    assert result["runtime_shadow"]["visible_response_source"] == "runtime_response"


def test_public_actions_must_point_to_existing_or_blocked_namespaced_capabilities() -> None:
    for manifest_path in Path("plugins").glob("*/manifest.yaml"):
        manifest = PluginManifest.from_file(manifest_path)
        declared = set(manifest.handles) | set(manifest.blocked_capabilities)
        for action in manifest.public_actions:
            assert "." in action.capability
            assert action.capability in declared
            if not action.enabled:
                assert action.disabled_reason


def test_public_endpoint_uses_runtime_response_and_keeps_legacy_shadow() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    result = layer.run(
        message=(
            "Cargue una denuncia desde la app y hace una semana sigue en tramite. "
            "Necesito el auto para trabajar."
        ),
        conversation_id="unified-public-runtime",
    )

    _assert_runtime_pipeline(result)
    _assert_clean_client_response(result["response"])
    assert result["active_plugin_id"] == "galicia.insurance"
    assert result["active_capability"] == "insurance.claims"
    assert result["response"].startswith("Entiendo.")
    assert "una semana" in result["response"]
    assert "Te oriento con el tramite" not in result["response"]
    assert result["legacy_response"]
    assert result["legacy_response"] != result["response"]
    assert result["runtime_shadow"]["divergence_count"] == 1


def test_public_trace_is_runtime_derived_and_not_developer_trace() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    result = layer.run(message="Que es la franquicia?", conversation_id="public-trace-runtime")

    _assert_runtime_pipeline(result)
    assert result["public_trace"]["trace_type"] == "public_trace.v1"
    assert result["developer_trace"] != result["public_trace"]
    assert "events" not in result["public_trace"]
    assert "payload" not in str(result["public_trace"]).lower()


def test_public_layer_no_longer_matches_baja_inside_trabajar() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    result = layer.run(
        message=(
            "Ayer cargue una denuncia desde la app y todavia nadie me escribio. "
            "Ademas necesito el auto para trabajar y no se si puedo mandarlo a reparar."
        ),
        conversation_id="regression-trabajar-unified",
    )

    _assert_runtime_pipeline(result)
    assert result["conversation_memory"]["generic_topic"] is None
    assert result["cognitive_turn"]["topic"] != "baja"
    assert "baja" not in result["response"].lower()


def test_public_session_preserves_conversation_state_by_conversation_id() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    conversation_id = "public-runtime-session"

    first = layer.run(message="Me chocaron ayer.", conversation_id=conversation_id)
    second = layer.run(message="No hubo lesionados.", conversation_id=conversation_id)

    _assert_runtime_pipeline(first)
    _assert_runtime_pipeline(second)
    first_turns = first["diagnostic_view"]["conversation_state_runtime"]["turn_count"]
    second_turns = second["diagnostic_view"]["conversation_state_runtime"]["turn_count"]
    assert first_turns == 1
    assert second_turns == 2
    assert second["conversation_memory"]["runtime_conversation_state"]["confirmed_facts"]


def test_action_driven_observability_uses_last_runtime_introspection_without_visible_chat() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    conversation_id = "observability-actions-runtime"
    layer.run(message="Que es CLEAS?", conversation_id=conversation_id)

    result = layer.run(message="", conversation_id=conversation_id, public_action_id="show_process")

    assert result["input_type"] == "action"
    assert result["chat_visible"] is False
    assert result["public_trace"]["source"] == "ACAOSRuntime"
    assert result["diagnostic_view"]["source"] == "ACAOSRuntime"
    assert result["runtime_shadow"]["available"] is False


def test_prepare_handoff_action_enters_runtime_pipeline() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    conversation_id = "handoff-action-runtime"
    layer.run(message="Me chocaron ayer.", conversation_id=conversation_id)

    result = layer.run(message="", conversation_id=conversation_id, public_action_id="prepare_handoff")

    _assert_runtime_pipeline(result)
    assert result["input_type"] == "action"
    assert result["public_action_id"] == "prepare_handoff"
    assert result["active_capability"] == "insurance.handoff.prepare"
    _assert_clean_client_response(result["response"])


def test_disabled_action_does_not_fake_real_system_access() -> None:
    layer = PublicConversationProductLayer.from_path("plugins")
    result = layer.run(message="consulta mi expediente", conversation_id="blocked-action", public_action_id="real_claim_status_lookup")

    assert result["input_type"] == "action"
    assert result["active_capability"] == "insurance.claim_status.lookup"
    assert result["diagnostic_view"]["status"] == "action_disabled"
    _assert_clean_client_response(result["response"])
    assert "expediente" not in result["response"].lower()


def test_rest_and_endpoint_api_keep_public_conversation_endpoint() -> None:
    api = RuntimeEndpointAPI()
    rest = RuntimeRESTAPI()
    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}

    assert "/public-conversation/product-layer" in paths
    assert "/public-conversation/product-layer/run" in paths
    assert rest.route("GET", "/public-conversation/product-layer").status_code == 200
    response = rest.route(
        "POST",
        "/public-conversation/product-layer/run",
        body={"message": "Que es CLEAS?", "conversation_id": "rest-runtime-public"},
    )
    assert response.status_code == 200
    assert response.payload["public_trace"]["source"] == "ACAOSRuntime"


def test_studio_keeps_public_endpoint_bindings_and_readme_encoding_is_clean() -> None:
    html = Path("studio/index.html").read_text(encoding="utf-8")
    readme = Path("README.md").read_text(encoding="utf-8")

    assert "/public-conversation/product-layer/run" in html
    assert "public_action_id" in html
    assert "publicActions" in html
    assert "Ã¢â€ â€œ" not in readme
