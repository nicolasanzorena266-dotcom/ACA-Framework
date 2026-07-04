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
from sdk.factory import build_galicia_runtime, process_message
from aca_kernel.core.events import Event


def _add_message_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--message", required=False, help="User message to process.")
    parser.add_argument("--conversation-id", default="cli", help="Conversation id.")
    parser.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    parser.add_argument("--events", action="store_true", help="Include internal runtime events.")
    parser.add_argument("--trace", action="store_true", help="Include execution trace in output.")


def _handle_message(args: argparse.Namespace) -> int:
    result = process_message(
        message=args.message,
        conversation_id=args.conversation_id,
        memory_path=args.memory,
        include_runtime_events=args.events,
    )
    if not args.trace:
        result.pop("execution_trace", None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0



def _handle_trace(args: argparse.Namespace) -> int:
    runtime = build_galicia_runtime(memory_path=args.memory)
    output = runtime.process_output(
        Event(
            type="user_message",
            payload=args.message,
            metadata={"conversation_id": args.conversation_id},
        )
    )
    trace = runtime.last_trace()
    if trace is None:
        raise RuntimeError("No execution trace available.")
    data = trace.to_json() if args.format == "json" else trace.to_dict()
    if args.format == "json":
        print(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0

def main() -> None:
    parser = argparse.ArgumentParser(description="Run ACA Framework from the command line.")
    subparsers = parser.add_subparsers(dest="command")

    doctor_parser = subparsers.add_parser("doctor", help="Validate the local ACA project.")
    doctor_parser.set_defaults(handler=lambda _args: print_json(run_doctor().to_dict()) or 0)

    version_parser = subparsers.add_parser("version", help="Print ACA project version metadata.")
    version_parser.set_defaults(handler=lambda _args: print_json(read_project_version().to_dict()) or 0)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect ACA runtime components.")
    inspect_subparsers = inspect_parser.add_subparsers(dest="inspect_target", required=True)
    runtime_parser = inspect_subparsers.add_parser("runtime", help="Inspect the runtime pipeline.")
    runtime_parser.set_defaults(handler=lambda _args: print_json(inspect_runtime().to_dict()) or 0)

    test_parser = subparsers.add_parser("test", help="Run the ACA test suite.")
    test_parser.set_defaults(handler=lambda _args: run_pytest())

    trace_parser = subparsers.add_parser("trace", help="Run a message and print its execution trace.")
    trace_parser.add_argument("mode", nargs="?", default="last", choices=["last", "export"], help="Trace action.")
    trace_parser.add_argument("--message", required=True, help="User message to trace.")
    trace_parser.add_argument("--conversation-id", default="cli", help="Conversation id.")
    trace_parser.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    trace_parser.add_argument("--format", choices=["dict", "json"], default="dict", help="Trace export format.")
    trace_parser.set_defaults(handler=_handle_trace)

    _add_message_args(parser)
    parser.set_defaults(handler=_handle_message)

    args = parser.parse_args()
    if args.command is None and not args.message:
        parser.error("the following arguments are required: --message")
    raise SystemExit(args.handler(args))


if __name__ == "__main__":
    main()
