def plan(context: dict) -> dict:
    return {
        "next_action": "respond",
        "strategy": "general_orientation",
        "requires_external_data": False,
    }
