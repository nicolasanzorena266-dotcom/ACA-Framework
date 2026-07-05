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


def test_rc3_billing_domain_does_not_route_to_insurance_claims() -> None:
    result = run_public_conversation_product_layer(
        message="Quiero revisar el estado de mi factura",
        conversation_id="rc3-billing-routing",
        root="plugins",
    )

    assert result["active_plugin_id"] == "generic.open_chat"
    assert result["active_capability"] == "generic.open_chat"
    assert result["active_capability"] != "insurance.claims"
    assert "factura" in result["response"].lower()
    _assert_clean(result["response"])


def test_rc3_explicit_domain_beats_generic_operational_words() -> None:
    billing = run_public_conversation_product_layer(
        message="Necesito saber el estado del trámite por el monto de mi factura",
        conversation_id="rc3-domain-precedence-billing",
        root="plugins",
    )
    glass = run_public_conversation_product_layer(
        message="Necesito saber el estado del trámite de cristales",
        conversation_id="rc3-domain-precedence-glass",
        root="plugins",
    )

    assert billing["active_capability"] == "generic.open_chat"
    assert "factura" in billing["response"].lower()
    assert glass["active_plugin_id"] == "galicia.insurance"
    assert glass["active_capability"] == "insurance.glass"
    assert "cristales" in glass["response"].lower()


def test_rc3_billing_fallback_does_not_fake_billing_capabilities() -> None:
    result = run_public_conversation_product_layer(
        message="Me dijeron que me iba a venir un valor pero me llegó la factura por un monto mayor",
        conversation_id="rc3-billing-no-fake-access",
        root="plugins",
    )

    response = result["response"].lower()
    assert result["active_capability"] == "generic.open_chat"
    assert "factura" in response
    assert "importe" in response or "monto" in response
    assert "ya consulté" not in response
    assert "estoy revisando" not in response
    assert "veo tu expediente" not in response
    _assert_clean(result["response"])


def test_rc3_repetition_marker_repairs_billing_context_instead_of_repeating_template() -> None:
    conversation_id = "rc3-repetition-billing"
    first = run_public_conversation_product_layer(
        message="Quiero revisar el estado de mi factura",
        conversation_id=conversation_id,
        root="plugins",
    )
    second = run_public_conversation_product_layer(
        message="ya te dije",
        conversation_id=conversation_id,
        root="plugins",
    )

    assert first["active_capability"] == "generic.open_chat"
    assert second["active_capability"] == "generic.open_chat"
    assert "ya lo dijiste" in second["response"].lower()
    assert "factura" in second["response"].lower()
    assert second["response"] != first["response"]
    assert "te oriento con el trámite" not in second["response"].lower()
    _assert_clean(second["response"])


def test_rc3_visible_response_reflects_semantic_core_of_user_message() -> None:
    cases = [
        ("Quiero revisar el estado de mi factura", {"factura", "pago", "vencimiento", "importe", "monto"}),
        ("fue cristales", {"cristales", "cristal"}),
    ]

    for index, (message, expected_terms) in enumerate(cases):
        result = run_public_conversation_product_layer(message=message, conversation_id=f"rc3-core-{index}", root="plugins")
        response = result["response"].lower()
        assert any(term in response for term in expected_terms), response
        _assert_clean(result["response"])


def test_rc3_studio_example_uses_galicia_cristales_flow_not_billing_status() -> None:
    html = Path("studio/index.html").read_text(encoding="utf-8")

    assert "Sprint 72B-RC3 Routing Repair" in html
    assert "const exampleMessages" in html
    assert "fue cristales" in html
    assert "48hs hábiles" in html
    assert "quiero hablar con una persona" in html
    assert "estado de mi factura" not in html
