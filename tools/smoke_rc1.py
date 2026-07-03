from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
KERNEL_PATH = ROOT / "kernel"

for path in [ROOT, KERNEL_PATH]:
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from sdk.factory import process_message


def main() -> None:
    cases = [
        "Hola",
        "Me chocaron ayer y el tercero no hizo la denuncia",
        "Que es CLEAS?",
        "Que es la franquicia?",
        "Ya aprobaron mi indemnizacion?",
    ]

    outputs = []
    for index, message in enumerate(cases, start=1):
        outputs.append(
            process_message(
                message,
                conversation_id=f"smoke-{index}",
                memory_path=".aca/smoke_memory.json",
            )
        )

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()