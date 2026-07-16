from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
KERNEL_ROOT = ROOT / "kernel"
if str(KERNEL_ROOT) not in sys.path:
    sys.path.insert(0, str(KERNEL_ROOT))

from aca_os.semantic_understanding_evaluation import (
    render_semantic_understanding_report,
    run_semantic_understanding_evaluation,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ACA's permanent Semantic Understanding Evaluation Suite."
    )
    parser.add_argument("--format", choices=("json", "markdown", "summary"), default="summary")
    parser.add_argument("--conversation", action="append", dest="conversation_ids")
    parser.add_argument("--profile", action="append", dest="profile_ids")
    args = parser.parse_args()

    result = run_semantic_understanding_evaluation(
        conversation_ids=args.conversation_ids,
        profile_ids=args.profile_ids,
    )
    if args.format == "markdown":
        print(render_semantic_understanding_report(result), end="")
    elif args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        output = {
            "contract": result["contract"],
            "benchmark": result["benchmark"],
            "engine": result["engine"],
            "summary": result["summary"],
            "distribution": result["distribution"],
            "report_hash": result["report_hash"],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
