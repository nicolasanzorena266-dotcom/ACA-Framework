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

from aca_os.verbalization_evaluation import (
    render_language_realization_benchmark_report,
    render_llm_verbalization_benchmark_report,
    render_llm_verbalization_provider_comparison,
    run_language_realization_benchmark,
    run_llm_verbalization_benchmark,
    run_llm_verbalization_provider_comparison,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ACA's LLM verbalization benchmark.")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--scenario", action="append", dest="scenario_ids")
    parser.add_argument(
        "--compare-providers",
        action="store_true",
        help="Compare OpenAI, Ollama and deterministic paths with fixed benchmark candidates.",
    )
    parser.add_argument(
        "--language-realization",
        action="store_true",
        help="Run semantic-preservation and language-quality scenarios.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use the configured live provider for the language-realization benchmark.",
    )
    args = parser.parse_args()

    if args.language_realization:
        result = run_language_realization_benchmark(
            scenario_ids=args.scenario_ids,
            live=args.live,
        )
    elif args.compare_providers:
        result = run_llm_verbalization_provider_comparison(scenario_ids=args.scenario_ids)
    else:
        result = run_llm_verbalization_benchmark(scenario_ids=args.scenario_ids)
    if args.format == "markdown":
        if args.language_realization:
            renderer = render_language_realization_benchmark_report
        elif args.compare_providers:
            renderer = render_llm_verbalization_provider_comparison
        else:
            renderer = render_llm_verbalization_benchmark_report
        print(renderer(result), end="")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
