from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


class MemoryStore:
    """Persistence boundary for ACA memory.

    This class stores memory as JSON so the first reference runtime can persist
    cognitive continuity without introducing a database dependency.
    """

    def load(self) -> Dict[str, Any]:
        raise NotImplementedError

    def save(self, data: Dict[str, Any]) -> None:
        raise NotImplementedError


class JsonMemoryStore(MemoryStore):
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {
                "working": {},
                "episodic": [],
                "semantic": {},
                "procedural": {},
            }

        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, data: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )