class PolicyDecision:
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"
    USE_TOOL = "USE_TOOL"
    ASK_CLARIFICATION = "ASK_CLARIFICATION"

class PolicyManager:
    def evaluate(self, state, event):
        return PolicyDecision.ALLOW
