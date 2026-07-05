from aca_os.demo_domain_flow import DemoDomainRuntimeFlowRunner
from aca_os.public_conversation_policy import compact_text


def test_public_conversation_runtime_continues_ticket_context_and_capabilities():
    runner = DemoDomainRuntimeFlowRunner()
    cid = "sprint71-public-conversation-runtime-ticket"

    ticket = runner.run(message="Necesito saber el estado del ticket 12345", conversation_id=cid)
    ack = runner.run(message="Bueno", conversation_id=cid)
    capabilities = runner.run(message="Podes haceeer algo mas?", conversation_id=cid)
    ai = runner.run(message="no tenees IA?", conversation_id=cid)

    assert "ticket 12345" in ticket["response"]
    assert "Sigo sobre el ticket 12345" in ack["response"]
    assert "ticket 12345" in capabilities["response"]
    assert "Puedo ayudarte de tres formas" in capabilities["response"]
    assert "no estoy conectado a una IA externa" in ai["response"]
    assert ticket["conversation_state"]["active_case_id"] == "12345"
    assert capabilities["conversation_state"]["active_topic"] == "ticket"
    assert capabilities["conversation_state"]["next_action_suggested"]


def test_public_conversation_runtime_uses_claim_context_for_followup_documents():
    runner = DemoDomainRuntimeFlowRunner()
    cid = "sprint71-public-conversation-runtime-claim"

    claim = runner.run(message="tuve un choque", conversation_id=cid)
    docs = runner.run(message="qué documentación necesito?", conversation_id=cid)

    assert "Lamento lo del choque" in claim["response"]
    assert "Para el choque" in docs["response"]
    assert "denuncia administrativa" in docs["response"]
    assert "fotos de los daños" in docs["response"]
    assert docs["conversation_state"]["active_claim_type"] == "choque"


def test_public_conversation_runtime_reformulates_instead_of_repeating_fallback():
    runner = DemoDomainRuntimeFlowRunner()
    cid = "sprint71-public-conversation-runtime-fallback"

    first = runner.run(message="asdfgh", conversation_id=cid)
    second = runner.run(message="zzzzzz", conversation_id=cid)

    assert first["response"] != second["response"]
    assert "Voy de nuevo" in second["response"]
    assert second["conversation_state"]["fallback_count"] == 0 or second["conversation_state"]["last_category"] == "fallback_reformulated"


def test_public_chat_ui_prioritizes_single_conversation_surface():
    html = open("studio/index.html", encoding="utf-8").read()

    assert "Runtime</span><strong>" not in html
    assert "Componentes</span><strong>" not in html
    assert "Módulos</span><strong>" not in html
    assert "Eventos</span><strong>" not in html
    assert ".main-grid { display: grid; grid-template-columns: 1fr" in html
    assert ".context-card { display: none;" in html
    assert "placeholder=\"Escribí tu consulta\"" in html
    assert "Ver proceso" in html
    assert "ACA en línea" in html


def test_public_text_compaction_handles_common_typos():
    assert compact_text("Podes haceeer algo mas?") == "podes hacer algo mas"
    assert "tenes ia" in compact_text("no tenees IA?")
