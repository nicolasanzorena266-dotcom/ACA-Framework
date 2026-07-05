def _value(context, key, default=None):
    if isinstance(context, dict):
        return context.get(key, default)
    return getattr(context, key, default)


def plan(context) -> dict:
    capability = _value(context, "capability", "insurance.claims")
    public_action_id = _value(context, "public_action_id")
    next_action = "prepare_handoff" if public_action_id == "prepare_handoff" or capability == "insurance.handoff.prepare" else "orient"
    return {
        "next_action": next_action,
        "strategy": "client_support_projection",
        "requires_external_data": False,
    }
