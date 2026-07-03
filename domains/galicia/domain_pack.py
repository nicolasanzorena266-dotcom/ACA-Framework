from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class GaliciaDomainPack:
    name: str = "galicia"
    scope: str = "informational_auto_claim_guidance"
    concepts: Dict[str, Any] = field(default_factory=dict)
    policies: Dict[str, Any] = field(default_factory=dict)
    scenarios: Dict[str, Any] = field(default_factory=dict)

    def context(self) -> Dict[str, Any]:
        return {
            "domain": self.name,
            "scope": self.scope,
            "concepts": self.concepts,
            "policies": self.policies,
            "scenarios": self.scenarios,
        }


def _load_json_dir(path: Path) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    if not path.exists():
        return data

    for file in sorted(path.glob("*.json")):
        data[file.stem] = json.loads(file.read_text(encoding="utf-8"))

    return data


def load_galicia_domain(base_path: str | Path | None = None) -> GaliciaDomainPack:
    base = Path(base_path) if base_path else Path(__file__).parent

    return GaliciaDomainPack(
        concepts=_load_json_dir(base / "concepts"),
        policies=_load_json_dir(base / "policies"),
        scenarios=_load_json_dir(base / "scenarios"),
    )