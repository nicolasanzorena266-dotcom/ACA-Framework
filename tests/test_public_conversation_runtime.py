from aca_os.demo_domain_flow import DemoDomainRuntimeFlowRunner


def test_public_conversation_runtime_continues_ticket_context_and_capabilities():
    runner = DemoDomainRuntimeFlowRunner()
    cid = "sprint71-public-conversation-runtime-ticket"

    ticket = runner.run(message="Necesito saber el estado del ticket 12345", conversation_id=cid)
    ack = runner.run(message="Bueno", conversation_id=cid)
    capabilities = runner.run(message="Podes haceeer algo mas?", conversation_id=cid)
    ai = runner.run(message="no tenees IA", conversation_id=cid)

    assert "ticket 12345" in ticket["response"]
    assert "Sigo sobre el ticket 12345" in ack["response"]
    assert "ticket 12345" in capabilities["response"]
    assert "Puedo ayudarte de tres formas" in capabilities["response"]
    assert "Puedo ayudarte de tres formas" in ai["response"]
    assert "ticket 12345" in ai["response"]


def test_public_chat_ui_prioritizes_single_conversation_surface():
    html = open("studio/index.html", encoding="utf-8").read()

    assert "Runtime</span><strong>" not in html
    assert "Componentes</span><strong>" not in html
    assert "Módulos</span><strong>" not in html
    assert "Eventos</span><strong>" not in html
    assert ".main-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(320px, 420px)" in html
    assert ".context-card { display: grid;" in html
    assert "Proceso y acciones" in html
    assert "Enviar" in html
