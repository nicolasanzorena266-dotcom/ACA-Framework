from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from aca_core.text import normalize_text


@dataclass(frozen=True)
class IntentMatch:
    intent: str
    confidence: float
    matched_terms: List[str] = field(default_factory=list)
    reason: str = "rule_match"

    def to_dict(self) -> Dict[str, object]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "matched_terms": list(self.matched_terms),
            "reason": self.reason,
        }


class IntentMatcher:
    """Zero-cost intent matcher.

    No LLM. No embeddings. No paid API.
    """

    def __init__(self, rules: Dict[str, Iterable[str]] | None = None):
        self.rules = {
            intent: [normalize_text(term) for term in terms]
            for intent, terms in (rules or DEFAULT_INTENT_RULES).items()
        }

    def match(self, text: object) -> IntentMatch:
        normalized = normalize_text(text)
        best_intent = "fallback"
        best_terms: List[str] = []
        best_score = 0.0

        for intent, terms in self.rules.items():
            matched = [term for term in terms if term and term in normalized]
            if not matched:
                continue

            score = min(1.0, len(matched) / max(1, min(4, len(terms))))

            if score > best_score:
                best_intent = intent
                best_terms = matched
                best_score = score

        if best_score == 0:
            return IntentMatch(
                intent="fallback",
                confidence=0.0,
                matched_terms=[],
                reason="no_rule_matched",
            )

        return IntentMatch(
            intent=best_intent,
            confidence=round(best_score, 2),
            matched_terms=best_terms,
        )


DEFAULT_INTENT_RULES: Dict[str, List[str]] = {
    "greeting": [
        "hola",
        "buenas",
        "buen dia",
        "buenas tardes",
        "buenas noches"
    ],
    "auto_claim_guidance": [
        "me chocaron",
        "choque",
        "siniestro",
        "accidente",
        "tercero",
        "denuncia"
    ],
    "concept_cleas": [
        "cleas",
        "convenio",
        "convenio cleas"
    ],
    "concept_franquicia": [
        "franquicia",
        "carta de franquicia"
    ],
    "concept_denuncia_administrativa": [
        "denuncia administrativa",
        "copia de denuncia"
    ],
    "real_claim_status": [
        "estado de mi siniestro",
        "estado del siniestro",
        "aprobaron",
        "rechazaron",
        "indemnizacion",
        "expediente",
        "numero de siniestro",
        "cuando me pagan"
    ],
    "human_request": [
        "asesor",
        "persona real",
        "supervisor",
        "representante",
        "humano"
    ],
}
