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

from aca_os.semantic_adversarial_evaluation import (
    render_adversarial_semantic_report,
    run_adversarial_semantic_evaluation,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Red-team SemanticAuthority without changing Runtime authority."
    )
    parser.add_argument("--format", choices=("json", "markdown", "summary"), default="summary")
    parser.add_argument("--conversation", action="append", dest="conversation_ids")
    parser.add_argument("--profile", action="append", dest="profile_ids")
    parser.add_argument("--skip-official", action="store_true")
    args = parser.parse_args()

    result = run_adversarial_semantic_evaluation(
        conversation_ids=args.conversation_ids,
        profile_ids=args.profile_ids,
        compare_official=not args.skip_official,
    )
    if args.format == "markdown":
        print(render_adversarial_semantic_report(result), end="")
    elif args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        output = {
            "contract": result["contract"],
            "benchmark": result["benchmark"],
            "engine": result["engine"],
            "metrics": result["metrics"],
            "confidence_calibration": result["confidence_calibration"],
            "benchmark_comparison": result["benchmark_comparison"],
            "recommendation": result["recommendation"],
            "error_classification": result["error_classification"],
            "report_hash": result["report_hash"],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
