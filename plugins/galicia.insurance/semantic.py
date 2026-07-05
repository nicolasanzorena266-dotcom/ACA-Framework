def analyze(message: str) -> dict:
    text = message.lower()
    if "cristal" in text or "vidrio" in text:
        return {"intent": "insurance.glass", "confidence": 0.8}
    if "accidente" in text or "choque" in text:
        return {"intent": "insurance.accident", "confidence": 0.75}
    return {"intent": "insurance.claims", "confidence": 0.55}
