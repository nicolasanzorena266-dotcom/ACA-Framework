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


def test_rc4_billing_transcript_reuses_explicit_amounts_and_progresses() -> None:
    conversation_id = "rc4-billing-amount-progression"
    messages = [
        "hola. me llego una factura con un importe mayor al que me solia venir",
        "me dijeron que me iba a llegar $110 y me llego $150000",
        "ya te dijee",
        "el importe",
        "si",
        "bue...",
    ]
    results = [
        run_public_conversation_product_layer(message=message, conversation_id=conversation_id, root="plugins")
        for message in messages
    ]
    responses = [result["response"] for result in results]

    assert results[0]["active_capability"] == "generic.open_chat"
    assert "factura" in responses[0].lower()
    assert "importe" in responses[0].lower()

    for response in responses[1:]:
        _assert_clean(response)
        assert "$110" in response
        assert "$150000" in response
        assert "factura" in response.lower()
        assert "importe" in response.lower()

    assert "ya lo dijiste" in responses[2].lower()
    assert "avancemos" in responses[3].lower() or "próximo paso" in responses[3].lower()
    assert "seguimos" in responses[4].lower() or "próximo paso" in responses[4].lower()
    assert "no te vuelvo a pedir" in responses[5].lower() or "no repito" in responses[5].lower()


def test_rc4_conversation_memory_exposes_billing_facts_without_full_csm() -> None:
    conversation_id = "rc4-memory-facts"
    run_public_conversation_product_layer(
        message="hola, me llegó una factura con un importe mayor",
        conversation_id=conversation_id,
        root="plugins",
    )
    result = run_public_conversation_product_layer(
        message="me dijeron que me iba a llegar $110 y me llego $150000",
        conversation_id=conversation_id,
        root="plugins",
    )

    memory = result["conversation_memory"]
    assert memory["domain"] == "billing"
    assert memory["issue_focus"] == "importe"
    assert memory["expected_amount"] == "$110"
    assert memory["received_amount"] == "$150000"
    assert memory["billing_issue"] in {"importe_incorrecto", "importe_mayor_al_esperado"}


def test_rc4_short_followups_do_not_reset_when_billing_context_is_sufficient() -> None:
    conversation_id = "rc4-billing-short-followups"
    run_public_conversation_product_layer(
        message="Me llegó una factura por un importe mayor",
        conversation_id=conversation_id,
        root="plugins",
    )
    run_public_conversation_product_layer(
        message="me dijeron $110 y me llegó $150000",
        conversation_id=conversation_id,
        root="plugins",
    )

    focus = run_public_conversation_product_layer(message="el importe", conversation_id=conversation_id, root="plugins")
    affirmation = run_public_conversation_product_layer(message="sí", conversation_id=conversation_id, root="plugins")

    for result in (focus, affirmation):
        response = result["response"]
        _assert_clean(response)
        assert result["active_capability"] == "generic.open_chat"
        assert "$110" in response
        assert "$150000" in response
        assert "contame" not in response.lower()


def test_rc4_cristales_share_question_and_repetition_stay_client_clean() -> None:
    conversation_id = "rc4-glass-clean-repair"
    run_public_conversation_product_layer(
        message="cargué una denuncia desde la app pero sigo sin tener respuesta",
        conversation_id=conversation_id,
        root="plugins",
    )
    run_public_conversation_product_layer(message="fue cristales", conversation_id=conversation_id, root="plugins")
    share = run_public_conversation_product_layer(
        message="claro. pero yo ya tengo la documentación, te la comparto a vos?",
        conversation_id=conversation_id,
        root="plugins",
    )
    repetition = run_public_conversation_product_layer(message="ya te dije eso", conversation_id=conversation_id, root="plugins")
    delay = run_public_conversation_product_layer(
        message="ya pasaron más de 48hs hábiles y nadie me contactó",
        conversation_id=conversation_id,
        root="plugins",
    )

    assert "no hace falta que me la compartas" in share["response"].lower()
    assert "no repito" in repetition["response"].lower()
    assert "48 horas hábiles" in delay["response"]
    for result in (share, repetition, delay):
        _assert_clean(result["response"])
        assert "tipo de" not in result["response"].lower()


def test_rc4_public_surface_removes_old_visible_technical_scaffolding() -> None:
    html = Path("studio/index.html").read_text(encoding="utf-8")

    assert "Sprint 72B-RC4 Memory Progression" in html
    assert "Sprint 64" not in html
    assert "max-height: 590px" not in html
    assert "Demo Polish" not in html
    assert "UX QA" not in html
    assert "Vínculo del runtime" not in html
    assert "Conectando…" not in html
    assert "Iniciando…" in html


def test_rc4_client_support_filter_blocks_demo_language() -> None:
    result = run_public_conversation_product_layer(
        conversation_id="rc4-disabled-demo-language",
        public_action_id="real_claim_status_lookup",
        root="plugins",
    )

    response = result["response"].lower()
    assert "demo" not in response
    assert "en esta demo" not in response
    assert "no está conectada acá" in response
    _assert_clean(result["response"])
