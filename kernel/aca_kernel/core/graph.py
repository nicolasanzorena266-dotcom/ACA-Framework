from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class OperationGraph:
    name: str
    operations: List[str]

    def __post_init__(self):
        if not self.operations:
            raise ValueError("OperationGraph must contain at least one operation.")
