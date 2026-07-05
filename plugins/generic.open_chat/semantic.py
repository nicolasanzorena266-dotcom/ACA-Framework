def analyze(message: str) -> dict:
    return {
        "intent": "open_chat",
        "confidence": 0.5 if message.strip() else 0.0,
        "facts": [],
    }
