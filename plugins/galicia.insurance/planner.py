def plan(context: dict) -> dict:
    return {
        "next_action": "orient",
        "strategy": "explain_limits_and_next_step",
        "requires_external_data": False,
    }
