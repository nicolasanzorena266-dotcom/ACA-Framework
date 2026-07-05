from aca_os.demo_domain_flow import DemoDomainRuntimeFlowRunner


def test_public_studio_chat_has_real_send_and_bounded_scroll():
    html = open("studio/index.html", encoding="utf-8").read()

    assert 'id="sendMessage"' in html
    assert "Enviar" in html
    assert "event.key === 'Enter'" in html
    assert "overflow-y: auto" in html
    assert "scrollTop = area.scrollHeight" in html


def test_public_studio_refresh_resets_visible_conversation():
    html = open("studio/index.html", encoding="utf-8").read()

    assert "Reiniciar" in html
    assert "function resetConversation()" in html
    assert "conversation.innerHTML = ''" in html
    assert "resetConversation();" in html


def test_public_studio_uses_human_spanish_labels_without_main_run_control():
    html = open("studio/index.html", encoding="utf-8").read()

    assert ">Run<" not in html
    assert "Copiar output" not in html
    assert "No hay código fuente" not in html
    assert "La decisión queda observable" not in html
    assert "Copiar resumen" in html
    assert "Ver proceso" in html


def test_demo_domain_flow_response_is_human_readable_not_raw_routing_dump():
    result = DemoDomainRuntimeFlowRunner().run(
        message="Necesito saber el estado del ticket 12345",
        conversation_id="sprint71-human-answer",
    )

    response = result["response"]
    assert "Revisé el ticket 12345" in response
    assert "Domain '" not in response
    assert "matched intent" not in response
    assert "selected flow" not in response
    assert "Entities:" not in response
