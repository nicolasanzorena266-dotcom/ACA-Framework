from __future__ import annotations

import argparse
from pathlib import Path

from aca_os.conversational_first_evaluation import (
    render_conversational_first_benchmark_report,
    run_conversational_first_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ACA's Conversational First benchmark")
    parser.add_argument("--benchmark", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_conversational_first_benchmark(args.benchmark)
    report = render_conversational_first_benchmark_report(result)
    if args.output:
        args.output.write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
