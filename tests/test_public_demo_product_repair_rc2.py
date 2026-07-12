from __future__ import annotations

import re
from pathlib import Path

from aca_os.public_conversation_product_layer import (
    CLIENT_TECHNICAL_FORBIDDEN,
    FALSE_OPERATIONAL_CLAIMS,
    run_public_conversation_product_layer,
)


HTML = Path("studio/index.html")


def _html() -> str:
    return HTML.read_text(encoding="utf-8")


def _assert_clean_client_text(text: str) -> None:
    lowered = text.lower()
    assert all(term not in lowered for term in CLIENT_TECHNICAL_FORBIDDEN)
    assert all(term not in lowered for term in FALSE_OPERATIONAL_CLAIMS)


def _assert_runtime_adapter(result: dict) -> None:
    assert result["public_trace"]["source"] == "ACAOSRuntime"
    assert result["diagnostic_view"]["source"] == "ACAOSRuntime"
    assert result["runtime_response"] == result["response"]
    assert result["conversation_memory"]["source"] == "runtime_conversation_state_projection"


def test_rc2_public_layout_is_chat_left_actions_right_without_cut_phone_shell() -> None:
    html = _html()

    assert "Sprint 72B-RC2 Product Repair" in html
    assert "chat-left-actions-right" in html
    assert "grid-template-columns: minmax(0, 1fr) minmax(320px, 420px)" in html
    assert ".sidebar { display: none; }" in html
    phone_frame_rule = re.search(r"\.phone-frame \{(?P<body>.*?)\n    \}", html, re.S).group("body")
    assert "height: min(700px, calc(100vh - 145px))" not in phone_frame_rule
    assert "aspect-ratio: 9 / 16" not in phone_frame_rule


def test_rc2_public_input_is_visible_on_desktop_and_mobile_acceptance_viewports() -> None:
    html = _html()

    assert "100dvh" in html
    assert "viewport 1366x768" in html
    assert "viewport 390x844" in html
    assert "grid-template-rows: auto minmax(0, 1fr) auto" in html
    assert ".input-strip" in html
    assert "minmax(520px, 62dvh)" in html
    assert ".phone-card { min-height: 520px; }" in html


def test_rc2_initial_client_chat_message_does_not_expose_framework_language() -> None:
    html = _html()

    assert "Hola, soy ACA" in html
    assert "No tengo conexiÃ³n real" not in html
    assert "no voy a inventar datos" not in html


def test_rc2_observability_actions_do_not_append_to_visible_chat() -> None:
    html = _html()

    show_process = re.search(r"function showProcessPanel\(\) \{(?P<body>.*?)\n    \}", html, re.S).group("body")
    show_diagnostic = re.search(r"function showDiagnosticPanel\(\) \{(?P<body>.*?)\n    \}", html, re.S).group("body")
    run_action = re.search(r"async function runPublicAction\(actionId\) \{(?P<body>.*?)\n    \}", html, re.S).group("body")

    assert "appendConversation" not in show_process
    assert "appendConversation" not in show_diagnostic
    assert "showProcessPanel(); return;" in run_action
    assert "showDiagnosticPanel(); return;" in run_action
    assert "appendConversation" not in run_action


def test_rc2_public_layer_keeps_runtime_session_across_rest_style_calls() -> None:
    conversation_id = "rc2-runtime-session"

    first = run_public_conversation_product_layer(message="Me chocaron ayer.", conversation_id=conversation_id, root="plugins")
    second = run_public_conversation_product_layer(message="No hubo lesionados.", conversation_id=conversation_id, root="plugins")

    _assert_runtime_adapter(first)
    _assert_runtime_adapter(second)
    assert second["diagnostic_view"]["conversation_state_runtime"]["turn_count"] == 2
    _assert_clean_client_text(second["response"])


def test_rc2_multiturn_public_flow_uses_runtime_not_legacy_projection() -> None:
    conversation_id = "rc2-runtime-manual-flow"
    messages = [
        "cargue una denuncia desde la app pero sigo sin tener respuesta",
        "fue cristales",
        "ya tengo la documentacion, te la comparto a vos?",
        "ya me dijiste eso",
        "cristales",
        "quiero hablar con una persona",
    ]
    results = [
        run_public_conversation_product_layer(message=message, conversation_id=conversation_id, root="plugins")
        for message in messages
    ]

    for result in results:
        _assert_runtime_adapter(result)
        _assert_clean_client_text(result["response"])
        assert result["runtime_response"] == result["response"]
    assert results[-1]["diagnostic_view"]["runtime_execution_engine"]["flow"] == "human_handoff"


def test_rc2_enabled_public_buttons_are_bound_to_real_actions() -> None:
    result = run_public_conversation_product_layer(message="Que es CLEAS?", conversation_id="rc2-actions", root="plugins")
    enabled_actions = [action for action in result["public_actions"] if action["enabled"]]

    assert enabled_actions
    for action in enabled_actions:
        response = run_public_conversation_product_layer(
            conversation_id="rc2-actions",
            public_action_id=action["id"],
            root="plugins",
        )
        assert response["contract"] == "public_conversation_product_layer.run.v1" or response["contract"] == "public_conversation_product_layer.reset.v1"
        if action["id"] in {"show_process", "show_diagnostic"}:
            assert response.get("chat_visible") is False
