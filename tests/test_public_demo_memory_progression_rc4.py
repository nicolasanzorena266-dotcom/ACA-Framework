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
    assert "contame el tema concreto" not in lowered


def _assert_runtime_adapter(result: dict) -> None:
    assert result["public_trace"]["source"] == "ACAOSRuntime"
    assert result["diagnostic_view"]["source"] == "ACAOSRuntime"
    assert result["runtime_response"] == result["response"]
    assert result["conversation_memory"]["source"] == "runtime_conversation_state_projection"


def test_rc4_public_memory_is_runtime_projection_not_product_memory_owner() -> None:
    conversation_id = "rc4-memory-runtime-projection"
    first = run_public_conversation_product_layer(
        message="Me chocaron ayer.",
        conversation_id=conversation_id,
        root="plugins",
    )
    second = run_public_conversation_product_layer(
        message="No hubo lesionados.",
        conversation_id=conversation_id,
        root="plugins",
    )

    for result in (first, second):
        _assert_runtime_adapter(result)
        _assert_clean(result["response"])

    memory = second["conversation_memory"]
    assert memory["source"] == "runtime_conversation_state_projection"
    assert memory["runtime_conversation_state"]["turn_count"] == 2
    assert "injuries" in str(memory["runtime_conversation_state"].get("confirmed_facts", {}))


def test_rc4_shadow_preserves_legacy_memory_for_comparison_only() -> None:
    conversation_id = "rc4-shadow-memory"
    result = run_public_conversation_product_layer(
        message="hola, me llego una factura con un importe mayor",
        conversation_id=conversation_id,
        root="plugins",
    )

    _assert_runtime_adapter(result)
    assert result["runtime_shadow"]["available"] is True
    assert result["legacy_response"]
    assert result["conversation_memory"]["legacy_shadow"]["retained_for"] == "shadow_validation_only"
    assert result["response"] != result["legacy_response"]


def test_rc4_observability_actions_do_not_create_visible_turns() -> None:
    conversation_id = "rc4-observability-runtime"
    run_public_conversation_product_layer(
        message="Que es CLEAS?",
        conversation_id=conversation_id,
        root="plugins",
    )
    result = run_public_conversation_product_layer(
        conversation_id=conversation_id,
        public_action_id="show_diagnostic",
        root="plugins",
    )

    assert result["chat_visible"] is False
    assert result["runtime_shadow"]["available"] is False
    assert result["diagnostic_view"]["source"] == "ACAOSRuntime"


def test_rc4_public_surface_removes_old_visible_technical_scaffolding() -> None:
    html = Path("studio/index.html").read_text(encoding="utf-8")

    assert "Sprint 72B-RC4 Memory Progression" in html
    assert "Sprint 64" not in html
    assert "max-height: 590px" not in html
    assert "Demo Polish" not in html
    assert "UX QA" not in html
    assert "VÃ­nculo del runtime" not in html
    assert "Conectandoâ€¦" not in html
    assert "Iniciando" in html


def test_rc4_client_support_filter_blocks_demo_language() -> None:
    result = run_public_conversation_product_layer(
        conversation_id="rc4-disabled-demo-language",
        public_action_id="real_claim_status_lookup",
        root="plugins",
    )

    response = result["response"].lower()
    assert "demo" not in response
    assert "en esta demo" not in response
    assert "no está conectada acá" in response or "no esta conectada aca" in response
    _assert_clean(result["response"])
