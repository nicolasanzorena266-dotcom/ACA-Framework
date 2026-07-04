from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
KERNEL_PATH = ROOT / "kernel"

for path in [ROOT, KERNEL_PATH]:
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from aca_os.runtime_api_endpoints import RuntimeEndpointAPI


def main() -> None:
    parser = argparse.ArgumentParser(description="ACA deterministic human test demo")
    parser.add_argument("--conversation-id", default="human-demo", help="Conversation id.")
    parser.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    parser.add_argument("--format", choices=("dict", "markdown"), default="dict", help="Output format.")
    args = parser.parse_args()

    result = RuntimeEndpointAPI().run_human_demo(
        conversation_id=args.conversation_id,
        memory_path=args.memory,
        format=args.format,
    )
    if isinstance(result, str):
        print(result, end="")
        return
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
