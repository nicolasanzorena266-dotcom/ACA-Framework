from abc import ABC, abstractmethod
from typing import Any, Dict
from aca_kernel.core.state import CognitiveState
from aca_kernel.core.events import Event
from aca_kernel.core.contract import OperationContract

class CognitiveOperation(ABC):
    name: str = "OPERATION"
    contract: OperationContract

    @abstractmethod
    def execute(self, state: CognitiveState, event: Event, context: Dict[str, Any] | None = None) -> CognitiveState:
        raise NotImplementedError
