from aca_core.text import normalize_text


def analyze(message: str, context=None) -> dict:
    normalized = normalize_text(message)
    return {
        "intent": "generic.open_chat",
        "capability": "generic.open_chat",
        "confidence": 0.5 if normalized else 0.0,
        "facts": [],
    }
