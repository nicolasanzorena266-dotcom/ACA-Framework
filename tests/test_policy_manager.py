from aca_kernel.core.events import Event
from aca_os.policy_manager import PolicyDecision, PolicyManager


DOMAIN_CONTEXT = {
    "concepts": {
        "cleas": {},
        "franquicia": {},
        "denuncia_administrativa": {},
    }
}


def test_policy_detects_accented_indemnizacion_as_escalation():
    result = PolicyManager().evaluate(
        None,
        Event(type="user_message", payload="Ya aprobaron mi indemnizaciÃ³n?"),
        domain_context=DOMAIN_CONTEXT,
    )

    assert result.decision == PolicyDecision.ESCALATE
    assert "no_crm_access" in result.triggered_rules


def test_policy_detects_domain_concept_with_accents():
    result = PolicyManager().evaluate(
        None,
        Event(type="user_message", payload="Necesito la denuncia administrativa"),
        domain_context=DOMAIN_CONTEXT,
    )

    assert result.decision == PolicyDecision.USE_TOOL
    assert result.tool_key == "denuncia_administrativa"


def test_policy_detects_human_request():
    result = PolicyManager().evaluate(
        None,
        Event(type="user_message", payload="Quiero hablar con un asesor"),
        domain_context=DOMAIN_CONTEXT,
    )

    assert result.decision == PolicyDecision.ESCALATE
    assert result.reason == "user_requested_human"