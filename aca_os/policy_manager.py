from dataclasses import dataclass, field
from typing import Any, Dict, List

from aca_os.text import normalize_text


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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "tool_key": self.tool_key,
            "triggered_rules": list(self.triggered_rules),
        }


class PolicyManager:
    def evaluate(
        self,
        state,
        event,
        domain_context: Dict[str, Any] | None = None,
    ) -> PolicyResult:
        text = normalize_text(event.payload)
        domain_context = domain_context or {}

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