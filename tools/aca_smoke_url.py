from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL_PATH = ROOT / "kernel"
for path in [ROOT, KERNEL_PATH]:
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from aca_os.public_url_smoke_test import (  # noqa: E402
    build_public_url_smoke_test_plan,
    run_public_url_smoke_test,
    validate_public_url_smoke_test_result,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ACA public URL smoke tests against a hosted demo URL.")
    parser.add_argument("public_base_url", help="Public hosted base URL, for example https://aca-public-web-demo.onrender.com")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout in seconds.")
    parser.add_argument("--plan", action="store_true", help="Print the smoke test plan without making network calls.")
    parser.add_argument("--validate", action="store_true", help="Validate the smoke test result and return non-zero on required failures.")
    args = parser.parse_args()

    payload = (
        build_public_url_smoke_test_plan(public_base_url=args.public_base_url)
        if args.plan
        else run_public_url_smoke_test(public_base_url=args.public_base_url, timeout_seconds=args.timeout)
    )
    if args.validate and not args.plan:
        validation = validate_public_url_smoke_test_result(payload)
        payload = {"smoke_test": payload, "validation": validation}
        if not validation["valid"]:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            raise SystemExit(1)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
