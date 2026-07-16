from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aca_os.semantic_firewall_plan import (
    build_semantic_firewall_refactoring_plan,
    select_first_eligible_migration_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the passive FW-1 Semantic Firewall refactoring plan."
    )
    parser.add_argument(
        "--format",
        choices=("summary", "json", "inventory", "matrix", "packages", "recomputation", "forecast", "selection", "mermaid"),
        default="summary",
    )
    parser.add_argument(
        "--prohibit-component",
        action="append",
        default=[],
        help="Exclude a component from automatic migration-package selection.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    plan = build_semantic_firewall_refactoring_plan(ROOT)
    rendered = _render(
        plan,
        args.format,
        prohibited_components=args.prohibit_component,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


def _render(
    plan: Any,
    output_format: str,
    *,
    prohibited_components: list[str],
) -> str:
    if output_format == "json":
        return _json(plan.to_dict())
    if output_format == "inventory":
        return _json(list(plan.inventory))
    if output_format == "matrix":
        return _json(list(plan.replacement_matrix))
    if output_format == "packages":
        return _json(
            {
                "migration_packages": list(plan.migration_packages),
                "elimination_order": list(plan.elimination_order),
            }
        )
    if output_format == "recomputation":
        return _json(plan.recomputation_report)
    if output_format == "forecast":
        return _json(list(plan.promotion_forecast))
    if output_format == "selection":
        return _json(
            select_first_eligible_migration_package(
                plan,
                prohibited_components=prohibited_components,
            )
        )
    if output_format == "mermaid":
        return plan.inventory_mermaid()
    return _json(
        {
            "contract": plan.to_dict()["contract"],
            "version": plan.to_dict()["version"],
            "authority_source_hash": plan.authority_source_hash,
            "authority_graph_hash": plan.authority_graph_hash,
            "plan_hash": plan.plan_hash,
            "summary": plan.summary,
            "elimination_order": list(plan.elimination_order),
            "promotion_forecast": list(plan.promotion_forecast),
        }
    )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    raise SystemExit(main())
