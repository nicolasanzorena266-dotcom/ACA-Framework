def analyze(message: str, context=None) -> dict:
    text = message.lower()
    if "persona" in text or "representante" in text or "deriv" in text:
        intent = "insurance.handoff.prepare"
    elif "cristal" in text or "vidrio" in text:
        intent = "insurance.glass"
    elif "accidente" in text or "choque" in text:
        intent = "insurance.accident"
    else:
        intent = "insurance.claims"
    confidence = 0.86 if intent == "insurance.glass" else 0.72
    return {
        "intent": intent,
        "capability": intent,
        "confidence": confidence,
        "signals": {"mentions_48h": "48" in text, "asks_person": "persona" in text or "representante" in text},
    }
