from aca_os.demo_domain_flow import DemoDomainRuntimeFlowRunner


def test_public_conversation_keeps_ticket_context_after_short_followup():
    runner = DemoDomainRuntimeFlowRunner()
    cid = "sprint71-rc5-ticket-context"

    first = runner.run(message="Necesito saber el estado del ticket 12345", conversation_id=cid)
    followup = runner.run(message="Bueno", conversation_id=cid)
    capability = runner.run(message="Qué podés hacer?", conversation_id=cid)

    assert "ticket 12345" in first["response"]
    assert "Sigo sobre el ticket 12345" in followup["response"]
    assert "ticket 12345" in capability["response"]
    assert "Puedo ayudarte de tres formas" in capability["response"]
    assert "Con lo que tengo cargado" not in followup["response"]


def test_public_conversation_handles_greeting_and_capabilities_without_fallback():
    runner = DemoDomainRuntimeFlowRunner()

    greeting = runner.run(message="Hola", conversation_id="sprint71-rc5-greeting")
    capabilities = runner.run(message="Que podes hacer?", conversation_id="sprint71-rc5-capabilities")

    assert "Hola" in greeting["response"]
    assert "Puedo orientarte" in greeting["response"]
    assert "Puedo ayudarte de tres formas" in capabilities["response"]
    assert "número de ticket" not in greeting["response"]


def test_public_conversation_uses_claim_context_for_documentation_followup():
    runner = DemoDomainRuntimeFlowRunner()
    cid = "sprint71-rc5-claim-context"

    claim = runner.run(message="Tuve un choque", conversation_id=cid)
    docs = runner.run(message="Qué documentación necesito?", conversation_id=cid)

    assert "Lamento lo del choque" in claim["response"]
    assert "Para el choque" in docs["response"]
    assert "denuncia administrativa" in docs["response"]
    assert "fotos de los daños" in docs["response"]


def test_public_studio_layout_prioritizes_story_chat_without_cutting_dashboard():
    html = open("studio/index.html", encoding="utf-8").read()

    assert "Runtime</span><strong>" not in html
    assert "Componentes</span><strong>" not in html
    assert "Eventos</span><strong>" not in html
    assert "width: min(46vh, 100%, 462px)" in html
    assert "height: min(calc(46vh * 16 / 9), calc(100vh - 154px), 820px)" in html
    assert "conversationId = `studio-domain-flow-${Date.now()}`" in html
    assert "ACA responde como asistente de atención" in html
