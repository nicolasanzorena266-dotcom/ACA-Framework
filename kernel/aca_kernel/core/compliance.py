from typing import List, Dict, Any
from aca_kernel.core.state import CognitiveState
from aca_kernel.core.contract import OperationContract

IGNORED_FIELDS = {"version", "timeline", "compliance"}

class ContractViolation(Exception):
    pass

def diff_state(before: CognitiveState, after: CognitiveState) -> List[str]:
    b = before.to_dict()
    a = after.to_dict()
    return [key for key in b if key not in IGNORED_FIELDS and b.get(key) != a.get(key)]

def validate_contract(before: CognitiveState, after: CognitiveState, contract: OperationContract) -> Dict[str, Any]:
    changed = diff_state(before, after)
    illegal = [field for field in changed if not contract.allows(field)]
    report = {
        "operation": contract.name,
        "passed": not illegal,
        "changed_fields": changed,
        "illegal_changes": illegal,
        "can_modify": list(contract.can_modify),
    }
    if illegal:
        raise ContractViolation(f"{contract.name} illegally modified {illegal}. Allowed: {contract.can_modify}")
    return report
