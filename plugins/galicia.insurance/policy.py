BLOCKED_CAPABILITIES = {
    "insurance.claim_status.lookup",
    "insurance.document.upload",
    "insurance.representative.transfer",
}


def _value(context, key, default=None):
    if isinstance(context, dict):
        return context.get(key, default)
    return getattr(context, key, default)


def authorize(context) -> dict:
    requested = _value(context, "capability")
    return {
        "allowed": requested not in BLOCKED_CAPABILITIES,
        "blocked_capabilities": sorted(BLOCKED_CAPABILITIES),
        "reason": None if requested not in BLOCKED_CAPABILITIES else "blocked_capability",
    }


def evaluate(context: dict) -> dict:
    return authorize(context)
