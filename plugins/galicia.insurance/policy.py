BLOCKED_CAPABILITIES = {
    "real_claim_status_lookup",
    "real_document_upload",
    "real_representative_transfer",
}


def evaluate(context: dict) -> dict:
    requested = context.get("requested_capability")
    return {
        "allowed": requested not in BLOCKED_CAPABILITIES,
        "blocked_capabilities": sorted(BLOCKED_CAPABILITIES),
        "limits": ["No se simula acceso a expedientes, cargas reales ni transferencia real."],
    }
