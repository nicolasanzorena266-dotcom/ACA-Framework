from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aca_os.authority_dependency_graph import build_authority_dependency_graph


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the passive SA-3.1 authority graph.")
    parser.add_argument("--repository-root", type=Path, default=None)
    parser.add_argument("--format", choices=("summary", "json", "mermaid"), default="summary")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    graph = build_authority_dependency_graph(args.repository_root)
    if args.format == "json":
        rendered = json.dumps(graph.to_dict(), ensure_ascii=False, indent=2)
    elif args.format == "mermaid":
        rendered = graph.to_mermaid()
    else:
        rendered = json.dumps(
            {
                "contract": graph.to_dict()["contract"],
                "version": graph.to_dict()["version"],
                "source_hash": graph.source_hash,
                "graph_hash": graph.graph_hash,
                "summary": graph.report["summary"],
                "promotion_order": graph.promotion_order,
                "ready_for_promotion": graph.report["ready_for_promotion"],
                "next_promotion_candidate": graph.report["next_promotion_candidate"],
            },
            ensure_ascii=False,
            indent=2,
        )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
