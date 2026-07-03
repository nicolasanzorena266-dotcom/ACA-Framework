from typing import Any, Dict
from aca_kernel.core.state import CognitiveState
from aca_kernel.core.events import Event
from aca_kernel.core.graph import OperationGraph
from aca_kernel.core.registry import OperationRegistry
from aca_kernel.core.compliance import validate_contract

class ACAKernel:
    def __init__(self, registry: OperationRegistry, enforce_contracts: bool = True):
        self.registry = registry
        self.enforce_contracts = enforce_contracts

    def run(self, event: Event, graph: OperationGraph, state: CognitiveState | None = None, context: Dict[str, Any] | None = None) -> CognitiveState:
        current = state or CognitiveState()
        current = current.evolve("COMPILE", selected_program=graph.name)
        for operation_name in graph.operations:
            operation = self.registry.get(operation_name)
            before = current
            after = operation.execute(current, event, context or {})
            if self.enforce_contracts:
                report = validate_contract(before, after, operation.contract)
                compliance = list(after.compliance)
                compliance.append(report)
                after = after.evolve("COMPLIANCE", compliance=compliance)
            current = after
        return current
