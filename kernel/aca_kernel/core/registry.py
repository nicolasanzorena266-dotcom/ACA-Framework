from typing import Dict
from aca_kernel.core.operation import CognitiveOperation

class OperationRegistry:
    def __init__(self):
        self._operations: Dict[str, CognitiveOperation] = {}

    def register(self, operation: CognitiveOperation) -> None:
        self._operations[operation.name] = operation

    def get(self, name: str) -> CognitiveOperation:
        if name not in self._operations:
            raise KeyError(f"Operation not registered: {name}")
        return self._operations[name]
