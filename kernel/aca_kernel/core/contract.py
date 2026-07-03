from dataclasses import dataclass, field
from typing import List

@dataclass(frozen=True)
class OperationContract:
    name: str
    can_modify: List[str] = field(default_factory=list)
    side_effects: bool = False
    deterministic: bool = True
    explainable: bool = True

    def allows(self, field: str) -> bool:
        return field in self.can_modify
