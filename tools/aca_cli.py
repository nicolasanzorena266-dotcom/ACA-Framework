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

from sdk.factory import process_message


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ACA Framework from the command line.")
    parser.add_argument("--message", required=True, help="User message to process.")
    parser.add_argument("--conversation-id", default="cli", help="Conversation id.")
    parser.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    args = parser.parse_args()

    result = process_message(
        message=args.message,
        conversation_id=args.conversation_id,
        memory_path=args.memory,
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()