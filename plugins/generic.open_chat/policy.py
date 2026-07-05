def authorize(context) -> dict:
    return {
        "allowed": True,
        "reason": None,
    }


def evaluate(context: dict) -> dict:
    return authorize(context)
