from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
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


def test_policy_authorizes_tool_lookup_from_execution_plan_without_reclassifying_text():
    state = CognitiveState(
        facts={
            "zero_cost_execution_plan": {
                "flow": "knowledge_lookup",
                "source_action": "knowledge_lookup",
                "kernel_program": "knowledge_lookup",
                "payload": {"tool_key": "cleas"},
                "steps": [
                    {"name": "policy", "required": True, "payload": {}},
                    {"name": "tool_lookup", "required": True, "payload": {"tool_key": "cleas"}},
                ],
            }
        }
    )

    result = PolicyManager().evaluate(
        state,
        Event(type="user_message", payload="texto irrelevante sin concepto"),
        domain_context=DOMAIN_CONTEXT,
    )

    assert result.decision == PolicyDecision.USE_TOOL
    assert result.tool_key == "cleas"
    assert result.reason == "execution_plan_tool_lookup_authorized"
    assert result.source == "execution_plan_policy"
    assert result.validations[0]["name"] == "execution_plan_present"


def test_policy_escalates_from_execution_plan_without_human_request_text():
    state = CognitiveState(
        facts={
            "zero_cost_execution_plan": {
                "flow": "human_handoff",
                "source_action": "human_handoff",
                "kernel_program": "fallback",
                "payload": {"reason": "explicit_human_request"},
                "steps": [{"name": "handoff", "required": True, "payload": {"reason": "explicit_human_request"}}],
            }
        }
    )

    result = PolicyManager().evaluate(
        state,
        Event(type="user_message", payload="texto irrelevante"),
        domain_context=DOMAIN_CONTEXT,
    )

    assert result.decision == PolicyDecision.ESCALATE
    assert result.reason == "user_requested_human"
    assert result.modifications[0]["type"] == "policy_interruption"
    assert result.source == "execution_plan_policy"


def test_policy_allows_guided_process_from_execution_plan():
    state = CognitiveState(
        facts={
            "zero_cost_execution_plan": {
                "flow": "guided_process",
                "source_action": "process_guidance",
                "kernel_program": "auto_claim_guidance",
                "payload": {"flow": "galicia_auto_claim_guidance"},
                "steps": [{"name": "kernel", "required": True, "payload": {}}],
            }
        }
    )

    result = PolicyManager().evaluate(
        state,
        Event(type="user_message", payload="quiero hablar con asesor pero el plan no lo pide"),
        domain_context=DOMAIN_CONTEXT,
    )

    assert result.decision == PolicyDecision.ALLOW
    assert result.reason == "execution_plan_authorized"
    assert result.source == "execution_plan_policy"
