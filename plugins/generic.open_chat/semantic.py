def analyze(message: str, context=None) -> dict:
    return {
        "intent": "generic.open_chat",
        "capability": "generic.open_chat",
        "confidence": 0.5 if message.strip() else 0.0,
        "facts": [],
    }
