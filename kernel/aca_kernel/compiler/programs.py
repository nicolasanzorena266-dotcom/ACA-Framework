from aca_kernel.core.graph import OperationGraph

PROGRAMS = {
    "greeting": OperationGraph("greeting", ["OBSERVE", "GENERATE", "VERIFY"]),
    "knowledge_lookup": OperationGraph("knowledge_lookup", ["OBSERVE", "GENERATE", "VERIFY"]),
    "auto_claim_guidance": OperationGraph("auto_claim_guidance", [
        "OBSERVE", "EXTRACT", "NORMALIZE", "RELATE", "INFER", "SCORE", "PLAN", "GENERATE", "VERIFY"
    ]),
    "fallback": OperationGraph("fallback", ["OBSERVE", "GENERATE", "VERIFY"]),
}
