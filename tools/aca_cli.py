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

from aca_os.dx import inspect_runtime, print_json, read_project_version, run_doctor, run_pytest
from sdk.factory import process_message


def _run_message(args: argparse.Namespace) -> int:
    result = process_message(
        message=args.message,
        conversation_id=args.conversation_id,
        memory_path=args.memory,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _run_doctor(_: argparse.Namespace) -> int:
    report = run_doctor(ROOT)
    print_json(report.to_dict())
    return 0 if report.ok else 1


def _run_version(_: argparse.Namespace) -> int:
    print_json(read_project_version(ROOT).to_dict())
    return 0


def _run_inspect(args: argparse.Namespace) -> int:
    if args.target == "runtime":
        print_json(inspect_runtime().to_dict())
        return 0
    raise SystemExit(f"Unknown inspect target: {args.target}")


def _run_test(_: argparse.Namespace) -> int:
    return run_pytest(ROOT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ACA Framework from the command line.")
    parser.add_argument("--message", help="User message to process.")
    parser.add_argument("--conversation-id", default="cli", help="Conversation id.")
    parser.add_argument("--memory", default=None, help="Optional JSON memory file path.")

    subparsers = parser.add_subparsers(dest="command")

    doctor = subparsers.add_parser("doctor", help="Check local ACA project health.")
    doctor.set_defaults(func=_run_doctor)

    version = subparsers.add_parser("version", help="Print ACA version and sprint metadata.")
    version.set_defaults(func=_run_version)

    inspect = subparsers.add_parser("inspect", help="Inspect ACA runtime structures.")
    inspect.add_argument("target", choices=["runtime"])
    inspect.set_defaults(func=_run_inspect)

    test = subparsers.add_parser("test", help="Run the local test suite.")
    test.set_defaults(func=_run_test)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.message:
        raise SystemExit(_run_message(args))

    func = getattr(args, "func", None)
    if func is None:
        parser.error("provide --message or one command: doctor, version, inspect, test")

    raise SystemExit(func(args))


if __name__ == "__main__":
    main()
