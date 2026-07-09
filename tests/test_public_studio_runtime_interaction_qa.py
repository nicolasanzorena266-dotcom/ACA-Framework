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
    assert "async function resetConversation(" in html
    assert "conversation.innerHTML = ''" in html
    assert "await resetConversation(false);" in html


def test_public_studio_uses_human_spanish_labels_without_main_run_control():
    html = open("studio/index.html", encoding="utf-8").read()

    assert ">Run<" not in html
    assert "Copiar output" not in html
    assert "No hay código fuente" not in html
    assert "La decisión queda observable" not in html
    assert "Resumen del turno" in html
    assert "Ver proceso" in html


def test_demo_domain_flow_response_is_human_readable_not_raw_routing_dump():
    result = DemoDomainRuntimeFlowRunner().run(
        message="Necesito saber el estado del ticket 12345",
        conversation_id="sprint71-human-answer",
    )

    response = result["response"]
    assert "no tengo conexión real" in response
    assert "ticket 12345" in response
    assert "estado actual, responsable y próximo paso" in response
    assert "Domain '" not in response
    assert "matched intent" not in response
    assert "selected flow" not in response
    assert "Entities:" not in response


def test_public_studio_handles_identity_and_ai_limit_questions_without_repeating_fallback():
    runner = DemoDomainRuntimeFlowRunner()

    identity = runner.run(message="sos un bot?", conversation_id="sprint71-identity")
    ai_limit = runner.run(message="solo podes responder eso? no tenes IA?", conversation_id="sprint71-ai-limit")
    confusion = runner.run(message="eh?", conversation_id="sprint71-confusion")

    assert "Soy ACA" in identity["response"]
    assert "asistente de atención" in identity["response"]
    assert "no estoy conectado a una IA externa" in ai_limit["response"]
    assert "no puedo hacer es consultar un caso real" in ai_limit["response"]
    assert "Me explico mejor" in confusion["response"]
    assert "Probá con un número de ticket" not in identity["response"]
    assert "Probá con un número de ticket" not in ai_limit["response"]


def test_public_studio_phone_has_real_cellphone_proportions_and_no_max_depth_leak():
    html = open("studio/index.html", encoding="utf-8").read()

    assert "width: 100%" in html
    assert "chat-left-actions-right" in html
    assert "phone-status { display: none; }" in html
    assert "<max-depth>" not in html
    assert "Probar ejemplo" in html
    assert "Runtime</span><strong>" not in html
    assert "Componentes</span><strong>" not in html
    assert "Simulador Runtime" not in html


def test_public_studio_removes_dashboard_cards_and_prioritizes_story_chat():
    html = open("studio/index.html", encoding="utf-8").read()

    assert ".cards { display: none; }" in html
    assert "phone-status { display: none; }" in html
    assert "chat-left-actions-right" in html
    assert "Resumen del turno" in html
    assert ">Runtime</span><strong>" not in html
    assert ">Componentes</span><strong>" not in html
    assert ">Eventos</span><strong>" not in html


def test_representative_answer_composer_orients_claims_without_runtime_jargon():
    result = DemoDomainRuntimeFlowRunner().run(
        message="tuve un choque",
        conversation_id="sprint71-claim-rep",
    )

    response = result["response"]
    assert "Lamento lo del choque" in response
    assert "denuncia administrativa" in response
    assert "fotos de los daños" in response
    assert "runtime" not in response.lower()
    assert "intent" not in response.lower()
