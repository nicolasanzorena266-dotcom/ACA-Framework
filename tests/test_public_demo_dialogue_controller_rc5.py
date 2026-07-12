from __future__ import annotations

from aca_os.public_conversation_product_layer import (
    CLIENT_TECHNICAL_FORBIDDEN,
    FALSE_OPERATIONAL_CLAIMS,
    run_public_conversation_product_layer,
)


def _assert_clean(text: str) -> None:
    lowered = text.lower()
    assert all(term not in lowered for term in CLIENT_TECHNICAL_FORBIDDEN)
    assert all(term not in lowered for term in FALSE_OPERATIONAL_CLAIMS)
    assert text.strip()


def _assert_runtime_adapter(result: dict) -> None:
    assert result["public_trace"]["source"] == "ACAOSRuntime"
    assert result["diagnostic_view"]["source"] == "ACAOSRuntime"
    assert result["runtime_response"] == result["response"]
    assert result["cognitive_turn"]["source"] == "ACAOSRuntime"
    assert result["conversation_memory"]["source"] == "runtime_conversation_state_projection"


def test_rc5_legacy_dialogue_controller_is_shadow_only() -> None:
    result = run_public_conversation_product_layer(
        message="quiero revisar una baja",
        conversation_id="rc5-controller-contract",
        root="plugins",
    )

    _assert_runtime_adapter(result)
    assert result["runtime_shadow"]["shadow_engine"] == "PublicConversationProductLayer.legacy"
    assert result["legacy_response"]
    assert result["legacy_response"] != result["response"]
    assert result["runtime_shadow"]["visible_response_source"] == "runtime_response"
    assert result["conversation_memory"]["legacy_shadow"]["retained_for"] == "shadow_validation_only"
    _assert_clean(result["response"])


def test_rc5_human_request_is_executed_by_runtime_not_dialogue_controller() -> None:
    conversation_id = "rc5-handoff-runtime"
    first = run_public_conversation_product_layer(
        message="quiero revisar una baja",
        conversation_id=conversation_id,
        root="plugins",
    )
    human = run_public_conversation_product_layer(
        message="Quiero hablar con alguien",
        conversation_id=conversation_id,
        root="plugins",
    )

    _assert_runtime_adapter(first)
    _assert_runtime_adapter(human)
    assert human["diagnostic_view"]["runtime_execution_engine"]["flow"] == "human_handoff"
    assert human["diagnostic_view"]["runtime_execution_engine"]["official_engine"] == "runtime_executor"
    assert human["legacy_response"]
    _assert_clean(human["response"])


def test_rc5_public_surface_remains_non_silent_across_short_followups() -> None:
    conversation_id = "rc5-no-silent-turn"
    messages = [
        "hola. me llego una factura con un importe mayor",
        "me dijeron $110 y me llego $150000",
        "bue...",
        "podes hacer algo mas?",
        "hola?",
        "bue...",
    ]

    results = [
        run_public_conversation_product_layer(message=message, conversation_id=conversation_id, root="plugins")
        for message in messages
    ]

    for result in results:
        _assert_runtime_adapter(result)
        _assert_clean(result["response"])
        assert result["diagnostic_view"]["conversation_state_runtime"]["available"] is True
    assert results[-1]["diagnostic_view"]["conversation_state_runtime"]["turn_count"] == len(messages)
