from aca_os.demo_domain_flow import DemoDomainRuntimeFlowRunner
from aca_os.public_conversation_contracts import SemanticParse, PolicyDecision, PlannerDecision, SupervisorResult


def test_rc10_contract_schemas_are_structured_and_auditable():
    parse = SemanticParse(
        intent="consultar_estado_o_plazo",
        topic="siniestro",
        user_goal="saber_si_hay_novedades",
        known_facts=("denuncia_cargada",),
        confidence=0.82,
        requires_tool=True,
        risk_level="medium",
    ).to_dict()
    policy = PolicyDecision(
        requested_action="consultar_estado_real",
        tool_required="claim_status_lookup",
        tool_available=False,
        authorization="blocked",
        fallback="explain_limit_and_offer_next_step",
    ).to_dict()
    plan = PlannerDecision(
        next_action="explain_limit",
        strategy="explain_tool_limit_then_orient",
        must_include=("limite_de_demo", "proximo_paso"),
        must_not_include=("estado_real_del_siniestro",),
    ).to_dict()
    supervisor = SupervisorResult(passes=True).to_dict()

    assert parse["intent"] == "consultar_estado_o_plazo"
    assert parse["confidence"] == 0.82
    assert parse["requires_tool"] is True
    assert policy["authorization"] == "blocked"
    assert policy["tool_available"] is False
    assert plan["next_action"] == "explain_limit"
    assert supervisor["passes"] is True


def test_rc10_multiturn_claim_followup_does_not_reset_or_repeat_steps():
    runner = DemoDomainRuntimeFlowRunner()
    cid = "sprint71-rc10-real-claim-flow"

    waiting = runner.run(message="cargué la denuncia desde la app pero no tengo novedades", conversation_id=cid)
    collision = runner.run(message="tuve un choque. cargue la denuncia en la app. pero sigo esperando", conversation_id=cid)
    already = runner.run(message="Si, ya lo hice a eso", conversation_id=cid)
    timeline = runner.run(message="Cuales son los plazos?", conversation_id=cid)
    docs = runner.run(message="documentacion", conversation_id=cid)
    sent_docs = runner.run(message="Ya la envie a la documentacion", conversation_id=cid)
    frustrated = runner.run(message="ya me dijiste mil veces eso", conversation_id=cid)
    handoff = runner.run(message="quiero hablar con una persona. derivame", conversation_id=cid)

    assert "qué tipo de siniestro" in waiting["response"] or "¿Fue choque" in waiting["response"]
    assert "choque" in collision["response"].lower()
    assert "análisis" in collision["response"].lower() or "analisis" in collision["response"].lower()
    assert "no tiene sentido repetirte" in already["response"]
    assert "72 horas hábiles" in timeline["response"] or "análisis" in timeline["response"].lower()
    assert "denuncia administrativa" in docs["response"]
    assert "siguiente paso" in sent_docs["response"] or "seguimiento" in sent_docs["response"]
    assert "no repetirte" in frustrated["response"] or "Cambio" in frustrated["response"] or "Tenés razón" in frustrated["response"]
    assert "Resumen para derivación" in handoff["response"]
    assert "choque" in handoff["response"]
    assert "denuncia" in handoff["response"].lower()

    assert handoff["public_trace"]["Qué entendí"]
    assert handoff["developer_trace"]["semantic_parse"]["intent"] == "solicitar_derivacion"
    assert handoff["developer_trace"]["policy_decision"]["authorization"] in {"authorized", "blocked", "needs_clarification"}


def test_rc10_policy_blocks_fake_tool_lookup_but_keeps_next_step():
    runner = DemoDomainRuntimeFlowRunner()
    result = runner.run(message="Necesito saber el estado del ticket 12345", conversation_id="sprint71-rc10-ticket-policy")

    policy = result["developer_trace"]["policy_decision"]
    assert policy["tool_required"] == "ticket_status_lookup"
    assert policy["tool_available"] is False
    assert policy["authorization"] == "blocked"
    assert "no tengo conexión real" in result["response"]
    assert "estado actual, responsable y próximo paso" in result["response"]
