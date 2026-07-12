from __future__ import annotations

from pathlib import Path

from aca_os.public_conversation_product_layer import (
    CLIENT_TECHNICAL_FORBIDDEN,
    FALSE_OPERATIONAL_CLAIMS,
    run_public_conversation_product_layer,
)


def _assert_clean(text: str) -> None:
    lowered = text.lower()
    assert all(term not in lowered for term in CLIENT_TECHNICAL_FORBIDDEN)
    assert all(term not in lowered for term in FALSE_OPERATIONAL_CLAIMS)


def _assert_runtime_adapter(result: dict) -> None:
    assert result["public_trace"]["source"] == "ACAOSRuntime"
    assert result["diagnostic_view"]["source"] == "ACAOSRuntime"
    assert result["runtime_response"] == result["response"]
    assert result["runtime_shadow"]["visible_response_source"] == "runtime_response"


def test_rc3_billing_message_no_longer_uses_plugin_routing_as_visible_authority() -> None:
    result = run_public_conversation_product_layer(
        message="Quiero revisar el estado de mi factura",
        conversation_id="rc3-billing-routing",
        root="plugins",
    )

    _assert_runtime_adapter(result)
    assert result["active_capability"] == "generic.open_chat"
    assert result["legacy_response"]
    assert result["response"] != result["legacy_response"]
    _assert_clean(result["response"])


def test_rc3_domain_precedence_is_shadow_metadata_not_response_generation() -> None:
    billing = run_public_conversation_product_layer(
        message="Necesito saber el estado del tramite por el monto de mi factura",
        conversation_id="rc3-domain-precedence-billing",
        root="plugins",
    )
    glass = run_public_conversation_product_layer(
        message="Necesito saber el estado del tramite de cristales",
        conversation_id="rc3-domain-precedence-glass",
        root="plugins",
    )

    _assert_runtime_adapter(billing)
    _assert_runtime_adapter(glass)
    assert billing["active_capability"] == "generic.open_chat"
    assert glass["active_plugin_id"] == "galicia.insurance"
    assert glass["active_capability"] in {"insurance.glass", "insurance.claims"}
    assert billing["runtime_shadow"]["available"] is True
    assert glass["runtime_shadow"]["available"] is True


def test_rc3_visible_response_comes_from_runtime_even_when_legacy_differs() -> None:
    result = run_public_conversation_product_layer(
        message="Me dijeron que me iba a venir un valor pero me llego la factura por un monto mayor",
        conversation_id="rc3-billing-no-fake-access",
        root="plugins",
    )

    _assert_runtime_adapter(result)
    assert result["runtime_response"] == result["response"]
    assert result["legacy_response"]
    assert result["runtime_shadow"]["divergence_count"] >= 0
    assert "ya consult" not in result["response"].lower()
    assert "estoy revisando" not in result["response"].lower()
    assert "veo tu expediente" not in result["response"].lower()
    _assert_clean(result["response"])


def test_rc3_repetition_uses_same_runtime_session() -> None:
    conversation_id = "rc3-repetition-runtime"
    first = run_public_conversation_product_layer(
        message="Me chocaron ayer",
        conversation_id=conversation_id,
        root="plugins",
    )
    second = run_public_conversation_product_layer(
        message="ya te dije",
        conversation_id=conversation_id,
        root="plugins",
    )

    _assert_runtime_adapter(first)
    _assert_runtime_adapter(second)
    assert second["diagnostic_view"]["conversation_state_runtime"]["turn_count"] == 2
    assert "te oriento con el tramite" not in second["response"].lower()
    _assert_clean(second["response"])


def test_rc3_studio_example_uses_galicia_cristales_flow_not_billing_status() -> None:
    html = Path("studio/index.html").read_text(encoding="utf-8")

    assert "Sprint 72B-RC3 Routing Repair" in html
    assert "const exampleMessages" in html
    assert "fue cristales" in html
    assert "48hs" in html
    assert "quiero hablar con una persona" in html
    assert "estado de mi factura" not in html
