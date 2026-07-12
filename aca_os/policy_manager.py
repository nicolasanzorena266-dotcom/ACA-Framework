from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from aca_core.text import normalize_text


class PolicyDecision:
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"
    USE_TOOL = "USE_TOOL"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"


@dataclass(frozen=True)
class PolicyResult:
    decision: str
    reason: str
    tool_key: str | None = None
    triggered_rules: List[str] = field(default_factory=list)
    plan_received: Dict[str, Any] | None = None
    validations: List[Dict[str, Any]] = field(default_factory=list)
    modifications: List[Dict[str, Any]] = field(default_factory=list)
    source: str = "legacy_text_policy"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "tool_key": self.tool_key,
            "triggered_rules": list(self.triggered_rules),
            "plan_received": dict(self.plan_received or {}),
            "validations": [dict(validation) for validation in self.validations],
            "modifications": [dict(modification) for modification in self.modifications],
            "source": self.source,
        }


class PolicyManager:
    def evaluate(
        self,
        state,
        event,
        domain_context: Dict[str, Any] | None = None,
    ) -> PolicyResult:
        domain_context = domain_context or {}
        execution_plan = _execution_plan_from_state(state)
        if execution_plan is not None:
            return self._evaluate_execution_plan(execution_plan, domain_context)

        text = normalize_text(event.payload)
        if self._explicit_human_request(text):
            return PolicyResult(
                decision=PolicyDecision.ESCALATE,
                reason="user_requested_human",
                triggered_rules=["human_requested"],
            )

        if self._requires_real_file_access(text):
            return PolicyResult(
                decision=PolicyDecision.ESCALATE,
                reason="request_requires_real_file_or_crm_access",
                triggered_rules=["no_real_claim_status", "no_crm_access"],
            )

        concept_key = self._detect_concept_key(text, domain_context)
        if concept_key:
            return PolicyResult(
                decision=PolicyDecision.USE_TOOL,
                reason="domain_concept_lookup_required",
                tool_key=concept_key,
                triggered_rules=["domain_concept_lookup"],
            )

        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason="no_policy_block",
        )

    def _evaluate_execution_plan(
        self,
        execution_plan: Mapping[str, Any],
        domain_context: Dict[str, Any],
    ) -> PolicyResult:
        flow = str(execution_plan.get("flow") or "fallback")
        source_action = str(execution_plan.get("source_action") or "")
        payload = execution_plan.get("payload", {})
        if not isinstance(payload, Mapping):
            payload = {}

        validations: List[Dict[str, Any]] = [
            {
                "name": "execution_plan_present",
                "result": "passed",
                "component": "policy_manager",
            }
        ]
        plan = dict(execution_plan)

        if flow == "knowledge_lookup" or source_action == "knowledge_lookup":
            tool_key = _tool_key_from_plan(execution_plan)
            validations.append(
                {
                    "name": "tool_key_present",
                    "result": "passed" if tool_key else "failed",
                    "tool_key": tool_key,
                    "component": "policy_manager",
                }
            )
            if not tool_key:
                return PolicyResult(
                    decision=PolicyDecision.ASK_CLARIFICATION,
                    reason="execution_plan_missing_tool_key",
                    triggered_rules=["plan_tool_key_missing"],
                    plan_received=plan,
                    validations=validations,
                    modifications=[
                        {
                            "type": "policy_restriction",
                            "reason": "tool_lookup_requires_tool_key",
                            "component": "policy_manager",
                        }
                    ],
                    source="execution_plan_policy",
                )

            tool_available = self._known_concept_available(tool_key, domain_context)
            validations.append(
                {
                    "name": "tool_available",
                    "result": "passed" if tool_available else "failed",
                    "tool_key": tool_key,
                    "component": "policy_manager",
                }
            )
            if not tool_available:
                return PolicyResult(
                    decision=PolicyDecision.ASK_CLARIFICATION,
                    reason="planned_tool_unavailable",
                    tool_key=tool_key,
                    triggered_rules=["planned_tool_unavailable"],
                    plan_received=plan,
                    validations=validations,
                    modifications=[
                        {
                            "type": "policy_restriction",
                            "reason": "tool_not_available_in_domain_context",
                            "tool_key": tool_key,
                            "component": "policy_manager",
                        }
                    ],
                    source="execution_plan_policy",
                )

            return PolicyResult(
                decision=PolicyDecision.USE_TOOL,
                reason="execution_plan_tool_lookup_authorized",
                tool_key=tool_key,
                triggered_rules=["plan_tool_lookup_authorized"],
                plan_received=plan,
                validations=validations,
                source="execution_plan_policy",
            )

        if flow in {"safe_escalation", "human_handoff"} or source_action in {"safe_escalation", "human_handoff"}:
            reason = str(payload.get("reason") or flow)
            triggered_rules = _escalation_rules_for(reason, flow)
            validations.append(
                {
                    "name": "escalation_required",
                    "result": "passed",
                    "reason": reason,
                    "component": "policy_manager",
                }
            )
            return PolicyResult(
                decision=PolicyDecision.ESCALATE,
                reason=_policy_reason_for_escalation(reason, flow),
                triggered_rules=triggered_rules,
                plan_received=plan,
                validations=validations,
                modifications=[
                    {
                        "type": "policy_interruption",
                        "reason": reason,
                        "component": "policy_manager",
                    }
                ],
                source="execution_plan_policy",
            )

        validations.append(
            {
                "name": "no_policy_restriction",
                "result": "passed",
                "flow": flow,
                "component": "policy_manager",
            }
        )
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason="execution_plan_authorized",
            triggered_rules=["plan_authorized"],
            plan_received=plan,
            validations=validations,
            source="execution_plan_policy",
        )

    def _explicit_human_request(self, text: str) -> bool:
        terms = [
            "persona real",
            "asesor",
            "asesora",
            "supervisor",
            "representante",
            "humano",
        ]
        return any(term in text for term in terms)

    def _requires_real_file_access(self, text: str) -> bool:
        status_terms = [
            "estado de mi siniestro",
            "estado del siniestro",
            "aprobaron",
            "aprobado",
            "rechazaron",
            "rechazado",
            "indemnizacion",
            "me van a pagar",
            "cuando me pagan",
            "expediente",
            "numero de siniestro",
            "nro de siniestro",
        ]
        return any(term in text for term in status_terms)

    def _known_concept_available(
        self,
        key: str,
        domain_context: Dict[str, Any],
    ) -> bool:
        concepts = domain_context.get("concepts", None)

        if concepts is None:
            return True

        if concepts == {}:
            return True

        return key in concepts

    def _detect_concept_key(
        self,
        text: str,
        domain_context: Dict[str, Any],
    ) -> str | None:
        if "cleas" in text or "convenio" in text:
            return "cleas" if self._known_concept_available("cleas", domain_context) else None

        if "franquicia" in text:
            return "franquicia" if self._known_concept_available("franquicia", domain_context) else None

        if "denuncia administrativa" in text or "copia de denuncia" in text:
            return "denuncia_administrativa" if self._known_concept_available("denuncia_administrativa", domain_context) else None

        return None


def _execution_plan_from_state(state: Any) -> Mapping[str, Any] | None:
    facts = getattr(state, "facts", None)
    if not isinstance(facts, Mapping):
        return None
    execution_plan = facts.get("zero_cost_execution_plan")
    if not isinstance(execution_plan, Mapping):
        return None
    if not execution_plan.get("flow"):
        return None
    return execution_plan


def _tool_key_from_plan(execution_plan: Mapping[str, Any]) -> str | None:
    payload = execution_plan.get("payload", {})
    if isinstance(payload, Mapping) and payload.get("tool_key"):
        return str(payload["tool_key"])
    steps = execution_plan.get("steps", [])
    if not isinstance(steps, list):
        return None
    for step in steps:
        if not isinstance(step, Mapping):
            continue
        if step.get("name") != "tool_lookup":
            continue
        step_payload = step.get("payload", {})
        if isinstance(step_payload, Mapping) and step_payload.get("tool_key"):
            return str(step_payload["tool_key"])
    return None


def _escalation_rules_for(reason: str, flow: str) -> List[str]:
    if reason == "explicit_human_request" or flow == "human_handoff":
        return ["human_requested"]
    if reason == "requires_real_claim_data":
        return ["no_real_claim_status", "no_crm_access"]
    return ["policy_escalation_required"]


def _policy_reason_for_escalation(reason: str, flow: str) -> str:
    if reason == "explicit_human_request" or flow == "human_handoff":
        return "user_requested_human"
    if reason == "requires_real_claim_data":
        return "request_requires_real_file_or_crm_access"
    return reason
