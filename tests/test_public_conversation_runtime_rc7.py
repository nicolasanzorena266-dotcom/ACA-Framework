from aca_os.demo_domain_flow import DemoDomainRuntimeFlowRunner


def test_public_conversation_handles_deductible_typo_and_documentation_followup():
    runner = DemoDomainRuntimeFlowRunner()
    cid = "sprint71-rc7-deductible-context"

    typo = runner.run(message="como seeria eeso dee la franquisia?", conversation_id=cid)
    simpler = runner.run(message="no entiendo", conversation_id=cid)
    docs = runner.run(message="que documentacion necesito?", conversation_id=cid)

    assert "franquicia" in typo["response"].lower()
    assert "Lo explico más simple" in simpler["response"]
    assert "carta o reclamo de franquicia" in docs["response"]
    assert "case id" not in docs["response"].lower()
    assert docs["conversation_state"]["active_claim_type"] == "franquicia"


def test_public_conversation_turns_frustration_into_ticket_client_answer():
    runner = DemoDomainRuntimeFlowRunner()
    cid = "sprint71-rc7-ticket-example"

    runner.run(message="case id 1516", conversation_id=cid)
    frustration = runner.run(message="no estas siendo de mucha ayuda", conversation_id=cid)
    example = runner.run(message="mostrame entonces como seria eso", conversation_id=cid)

    assert "ticket 1516" in frustration["response"]
    assert "una respuesta de atención" in frustration["response"]
    assert "ticket 1516" in example["response"]
    assert "respondiera algo así" not in example["response"]
    assert "estado del caso" in example["response"]
    assert "estado verdadero" not in example["response"]


def test_public_studio_layout_uses_single_public_chat_surface():
    html = open("studio/index.html", encoding="utf-8").read()

    assert "chat-left-actions-right" in html
    assert "viewport 1366x768" in html
    assert "viewport 390x844" in html
    assert "Proceso y acciones" in html
    assert "Runtime</span><strong>" not in html
    assert "Componentes</span><strong>" not in html
