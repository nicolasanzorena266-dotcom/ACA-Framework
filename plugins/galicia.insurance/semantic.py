BILLING_TERMS = {
    "factura",
    "facturación",
    "facturacion",
    "pago",
    "vencimiento",
    "importe",
    "monto",
    "cobro",
    "deuda",
}


def analyze(message: str, context=None) -> dict:
    text = message.lower()
    if any(term in text for term in BILLING_TERMS):
        return {"intent": None, "confidence": 0.0, "domain_match": False}
    if "cristal" in text or "vidrio" in text or "parabrisas" in text:
        return {"intent": "insurance.glass", "confidence": 0.86, "domain_match": True}
    if "accidente" in text or "choque" in text or "colisión" in text or "colision" in text:
        return {"intent": "insurance.accident", "confidence": 0.78, "domain_match": True}
    if any(term in text for term in ("siniestro", "denuncia", "robo", "franquicia", "póliza", "poliza")):
        return {"intent": "insurance.claims", "confidence": 0.68, "domain_match": True}
    return {"intent": None, "confidence": 0.0, "domain_match": False}
