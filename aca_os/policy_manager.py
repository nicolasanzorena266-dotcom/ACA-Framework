class PolicyDecision:
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"
    USE_TOOL = "USE_TOOL"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"


def _normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    for a, b in {"Ã¡": "a", "Ã©": "e", "Ã­": "i", "Ã³": "o", "Ãº": "u", "Ã±": "n"}.items():
        text = text.replace(a, b)
    return text


class PolicyManager:
    def evaluate(self, state, event):
        text = _normalize_text(str(event.payload))

        if "cleas" in text or "convenio" in text:
            return PolicyDecision.USE_TOOL

        if "supervisor" in text or "persona real" in text or "asesor" in text:
            return PolicyDecision.ESCALATE

        return PolicyDecision.ALLOW
