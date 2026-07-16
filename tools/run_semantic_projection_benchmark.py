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

from aca_os.semantic_projection_evaluation import (
    render_semantic_projection_benchmark_report,
    run_semantic_projection_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ACA's SA-2 Semantic Projection Shadow benchmark."
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--scenario", action="append", dest="scenario_ids")
    args = parser.parse_args()

    result = run_semantic_projection_benchmark(scenario_ids=args.scenario_ids)
    if args.format == "markdown":
        print(render_semantic_projection_benchmark_report(result), end="")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
