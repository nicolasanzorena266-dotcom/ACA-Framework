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
from aca_os.session import ExecutionSession


def _add_message_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--message", required=False, help="User message to process.")
    parser.add_argument("--conversation-id", default="cli", help="Conversation id.")
    parser.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    parser.add_argument("--events", action="store_true", help="Include internal runtime events.")
    parser.add_argument("--trace", action="store_true", help="Include execution trace in output.")
    parser.add_argument("--introspection", action="store_true", help="Include runtime introspection snapshot.")
    parser.add_argument("--studio", action="store_true", help="Include ACA Studio MVP view.")
    parser.add_argument("--save-session", default=None, help="Optional path to persist the execution session.")


def _handle_message(args: argparse.Namespace) -> int:
    result = process_message(
        message=args.message,
        conversation_id=args.conversation_id,
        memory_path=args.memory,
        include_runtime_events=args.events,
        include_introspection=args.introspection,
        include_studio=args.studio,
        save_session_path=args.save_session,
    )
    if not args.trace:
        result.pop("execution_trace", None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0



def _run_runtime_for_inspection(args: argparse.Namespace):
    runtime = build_galicia_runtime(memory_path=args.memory)
    output = runtime.process_output(
        Event(
            type="user_message",
            payload=args.message,
            metadata={"conversation_id": args.conversation_id},
        )
    )
    return runtime, output


def _handle_trace(args: argparse.Namespace) -> int:
    runtime, output = _run_runtime_for_inspection(args)
    trace = runtime.last_trace()
    if trace is None:
        raise RuntimeError("No execution trace available.")
    data = trace.to_json() if args.format == "json" else trace.to_dict()
    if args.format == "json":
        print(data)
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0

def _handle_inspect_session(args: argparse.Namespace) -> int:
    runtime, output = _run_runtime_for_inspection(args)
    print_json(runtime.inspect_runtime().to_dict())
    return 0


def _handle_studio(args: argparse.Namespace) -> int:
    runtime, output = _run_runtime_for_inspection(args)
    data = runtime.export_studio(format=args.format)
    if args.output:
        Path(args.output).write_text(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print_json({"status": "written", "path": args.output, "format": args.format})
        return 0
    if isinstance(data, str):
        print(data)
    else:
        print_json(data)
    return 0


def _handle_session_save(args: argparse.Namespace) -> int:
    runtime, output = _run_runtime_for_inspection(args)
    path = runtime.save_last_session(args.output)
    print_json({"status": "written", "path": path, "session": runtime.last_session().summary()})
    return 0


def _handle_session_replay(args: argparse.Namespace) -> int:
    runtime = build_galicia_runtime(memory_path=args.memory)
    output = runtime.replay_session(args.path)
    print_json(output.to_dict())
    return 0


def _handle_session_compare(args: argparse.Namespace) -> int:
    runtime = build_galicia_runtime()
    print_json(runtime.compare_sessions(args.left, args.right))
    return 0


def _handle_session_show(args: argparse.Namespace) -> int:
    session = ExecutionSession.load(args.path)
    print_json(session.summary() if args.summary else session.to_dict())
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

    session_parser = inspect_subparsers.add_parser("session", help="Run a message and inspect the runtime session.")
    session_parser.add_argument("--message", required=True, help="User message to inspect.")
    session_parser.add_argument("--conversation-id", default="cli", help="Conversation id.")
    session_parser.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    session_parser.set_defaults(handler=_handle_inspect_session)

    test_parser = subparsers.add_parser("test", help="Run the ACA test suite.")
    test_parser.set_defaults(handler=lambda _args: run_pytest())

    trace_parser = subparsers.add_parser("trace", help="Run a message and print its execution trace.")
    trace_parser.add_argument("mode", nargs="?", default="last", choices=["last", "export"], help="Trace action.")
    trace_parser.add_argument("--message", required=True, help="User message to trace.")
    trace_parser.add_argument("--conversation-id", default="cli", help="Conversation id.")
    trace_parser.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    trace_parser.add_argument("--format", choices=["dict", "json"], default="dict", help="Trace export format.")
    trace_parser.set_defaults(handler=_handle_trace)

    studio_parser = subparsers.add_parser("studio", help="Run a message and print the ACA Studio MVP view.")
    studio_parser.add_argument("--message", required=True, help="User message to inspect.")
    studio_parser.add_argument("--conversation-id", default="cli", help="Conversation id.")
    studio_parser.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    studio_parser.add_argument("--format", choices=["dict", "json", "html"], default="dict", help="Studio export format.")
    studio_parser.add_argument("--output", default=None, help="Optional file path for Studio export.")
    studio_parser.set_defaults(handler=_handle_studio)

    session_parser = subparsers.add_parser("session", help="Persist, replay and compare execution sessions.")
    session_subparsers = session_parser.add_subparsers(dest="session_command", required=True)

    session_save = session_subparsers.add_parser("save", help="Run a message and save its execution session.")
    session_save.add_argument("--message", required=True, help="User message to execute.")
    session_save.add_argument("--conversation-id", default="cli", help="Conversation id.")
    session_save.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    session_save.add_argument("--output", required=True, help="Destination .aca.json session file.")
    session_save.set_defaults(handler=_handle_session_save)

    session_show = session_subparsers.add_parser("show", help="Show a saved execution session.")
    session_show.add_argument("path", help="Session file path.")
    session_show.add_argument("--summary", action="store_true", help="Print only the session summary.")
    session_show.set_defaults(handler=_handle_session_show)

    session_replay = session_subparsers.add_parser("replay", help="Replay a saved execution session.")
    session_replay.add_argument("path", help="Session file path.")
    session_replay.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    session_replay.set_defaults(handler=_handle_session_replay)

    session_compare = session_subparsers.add_parser("compare", help="Compare two saved execution sessions.")
    session_compare.add_argument("left", help="Left session file path.")
    session_compare.add_argument("right", help="Right session file path.")
    session_compare.set_defaults(handler=_handle_session_compare)

    _add_message_args(parser)
    parser.set_defaults(handler=_handle_message)

    args = parser.parse_args()
    if args.command is None and not args.message:
        parser.error("the following arguments are required: --message")
    raise SystemExit(args.handler(args))


if __name__ == "__main__":
    main()
