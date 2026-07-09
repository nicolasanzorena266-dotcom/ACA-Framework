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


def test_rc5_dialogue_controller_exposes_structured_turn_contract() -> None:
    result = run_public_conversation_product_layer(
        message="quiero revisar una baja",
        conversation_id="rc5-controller-contract",
        root="plugins",
    )

    turn = result["cognitive_turn"]
    assert turn["dialogue_act"] == "user_named_topic"
    assert turn["topic"] == "baja"
    assert turn["next_action"] == "ask_service_request_scope"
    assert "dialogue_controller" in result.get("contract", "") or "cognitive_turn" in result
    assert result["conversation_memory"]["generic_topic"] == "baja"
    assert result["response"]


def test_rc5_generic_baja_is_topic_and_human_request_prepares_summary() -> None:
    conversation_id = "rc5-baja-handoff"
    first = run_public_conversation_product_layer(
        message="quiero revisar una baja",
        conversation_id=conversation_id,
        root="plugins",
    )
    repetition = run_public_conversation_product_layer(
        message="ya te dije",
        conversation_id=conversation_id,
        root="plugins",
    )
    human = run_public_conversation_product_layer(
        message="Quiero hablar con alguien",
        conversation_id=conversation_id,
        root="plugins",
    )

    assert first["active_capability"] == "generic.open_chat"
    assert "baja" in first["response"].lower()
    assert "tema concreto" not in first["response"].lower()
    assert "baja" in repetition["response"].lower()
    assert "no vuelvo" in repetition["response"].lower() or "no repito" in repetition["response"].lower()
    assert "no puedo transferirte" in human["response"].lower()
    assert "baja" in human["response"].lower()
    assert human["cognitive_turn"]["dialogue_act"] == "user_requests_human"
    for result in (first, repetition, human):
        _assert_clean(result["response"])


def test_rc5_billing_confirmations_and_completed_steps_advance_instead_of_repeating() -> None:
    conversation_id = "rc5-billing-next-action"
    run_public_conversation_product_layer(
        message="hola. me llego una factura con un importe mayor al que me solia venir",
        conversation_id=conversation_id,
        root="plugins",
    )
    run_public_conversation_product_layer(
        message="me dijeron que me iba a llegar $110 y me llego $150000",
        conversation_id=conversation_id,
        root="plugins",
    )
    evidence = run_public_conversation_product_layer(
        message="Si, lo tengo aca",
        conversation_id=conversation_id,
        root="plugins",
    )
    reviewed = run_public_conversation_product_layer(
        message="ya lo revise",
        conversation_id=conversation_id,
        root="plugins",
    )

    assert evidence["cognitive_turn"]["dialogue_act"] == "user_confirmed_evidence"
    assert evidence["cognitive_turn"]["next_action"] == "offer_claim_draft"
    assert "armar el reclamo" in evidence["response"].lower()
    assert "$110" in evidence["response"] and "$150000" in evidence["response"]
    assert reviewed["cognitive_turn"]["dialogue_act"] == "user_completed_step"
    assert "ya revisaste" in reviewed["response"].lower()
    assert "siguiente paso" in reviewed["response"].lower()
    assert "revisar si corresponde" not in reviewed["response"].lower()
    _assert_clean(evidence["response"])
    _assert_clean(reviewed["response"])


def test_rc5_user_selects_offered_billing_options_and_menu_does_not_repeat() -> None:
    conversation_id = "rc5-billing-option-selection"
    run_public_conversation_product_layer(message="factura", conversation_id=conversation_id, root="plugins")
    reclamo = run_public_conversation_product_layer(message="reclamo", conversation_id=conversation_id, root="plugins")
    iniciado = run_public_conversation_product_layer(message="un reclamo ya iniciado", conversation_id=conversation_id, root="plugins")
    vencimiento = run_public_conversation_product_layer(message="vencimiento", conversation_id=conversation_id, root="plugins")

    assert reclamo["cognitive_turn"]["dialogue_act"] == "user_selected_option"
    assert "reclamo de factura" in reclamo["response"].lower()
    assert "ya iniciado" in iniciado["response"].lower()
    assert "vencimiento" in vencimiento["response"].lower()
    for result in (reclamo, iniciado, vencimiento):
        response = result["response"].lower()
        assert "decime si querés revisar importe" not in response
        assert "para avanzar" not in response or "preparar" in response or "ordenar" in response
        _assert_clean(result["response"])


def test_rc5_capability_ping_and_frustration_never_create_silent_turns_or_repeated_repair() -> None:
    conversation_id = "rc5-no-silent-turn"
    run_public_conversation_product_layer(
        message="hola. me llego una factura con un importe mayor",
        conversation_id=conversation_id,
        root="plugins",
    )
    run_public_conversation_product_layer(
        message="me dijeron $110 y me llegó $150000",
        conversation_id=conversation_id,
        root="plugins",
    )
    first_frustration = run_public_conversation_product_layer(message="bue...", conversation_id=conversation_id, root="plugins")
    capabilities = run_public_conversation_product_layer(message="podes hacer algo mas?", conversation_id=conversation_id, root="plugins")
    ping = run_public_conversation_product_layer(message="hola?", conversation_id=conversation_id, root="plugins")
    second_frustration = run_public_conversation_product_layer(message="bue...", conversation_id=conversation_id, root="plugins")

    assert "armar" in capabilities["response"].lower()
    assert "resumen" in capabilities["response"].lower()
    assert "no puedo consultar" in capabilities["response"].lower()
    assert "estoy acá" in ping["response"].lower()
    assert first_frustration["response"] != second_frustration["response"]
    for result in (first_frustration, capabilities, ping, second_frustration):
        assert result["response"].strip()
        _assert_clean(result["response"])
