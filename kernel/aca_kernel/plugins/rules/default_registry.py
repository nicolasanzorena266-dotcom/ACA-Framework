from aca_kernel.core.registry import OperationRegistry
from aca_kernel.operations.basic import Observe, Extract, Normalize, Relate, Infer, Score, Plan, Generate, Verify

def build_default_registry() -> OperationRegistry:
    registry = OperationRegistry()
    for operation in [Observe(), Extract(), Normalize(), Relate(), Infer(), Score(), Plan(), Generate(), Verify()]:
        registry.register(operation)
    return registry
