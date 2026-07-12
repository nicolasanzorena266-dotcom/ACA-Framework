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
from aca_os.evaluation import (
    render_cognitive_benchmark_report,
    run_cognitive_conversation_benchmark,
)
from aca_os.runtime_cli import RuntimeCLI


def _write_or_print(data, *, output: str | None = None) -> None:
    if isinstance(data, str):
        rendered = data
    else:
        rendered = json.dumps(data, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
        print_json({"status": "written", "path": output})
        return
    print(rendered)


def _message_args(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    parser.add_argument("--message", required=required, help="User message to process.")
    parser.add_argument("--conversation-id", default="cli", help="Conversation id.")
    parser.add_argument("--memory", default=None, help="Optional JSON memory file path.")


def _format_arg(parser: argparse.ArgumentParser, values=("dict", "json"), default="dict") -> None:
    parser.add_argument("--format", choices=values, default=default, help="Output format.")


def _handle_run(args: argparse.Namespace) -> int:
    cli = RuntimeCLI()
    result = cli.run(
        message=args.message,
        conversation_id=args.conversation_id,
        memory_path=args.memory,
        include_events=args.events,
        include_trace=args.trace,
        include_introspection=args.introspection,
        include_studio=args.studio,
        save_session_path=args.save_session,
    )
    _write_or_print(result)
    return 0


def _handle_status(args: argparse.Namespace) -> int:
    _write_or_print(RuntimeCLI().status(memory_path=args.memory))
    return 0


def _handle_components(args: argparse.Namespace) -> int:
    _write_or_print(RuntimeCLI().components(format=args.format, memory_path=args.memory))
    return 0


def _handle_plugins(args: argparse.Namespace) -> int:
    _write_or_print(
        RuntimeCLI().plugins(
            root=args.root,
            strict=args.strict,
            format=args.format,
            memory_path=args.memory,
        )
    )
    return 0


def _handle_metrics(args: argparse.Namespace) -> int:
    _write_or_print(
        RuntimeCLI().metrics(
            message=args.message,
            conversation_id=args.conversation_id,
            memory_path=args.memory,
            format=args.format,
        )
    )
    return 0


def _handle_trace(args: argparse.Namespace) -> int:
    _write_or_print(
        RuntimeCLI().trace(
            message=args.message,
            conversation_id=args.conversation_id,
            memory_path=args.memory,
            format=args.format,
        )
    )
    return 0


def _handle_inspect_session(args: argparse.Namespace) -> int:
    _write_or_print(
        RuntimeCLI().introspection(
            message=args.message,
            conversation_id=args.conversation_id,
            memory_path=args.memory,
            format="dict",
        )
    )
    return 0


def _handle_inspect_runtime(args: argparse.Namespace) -> int:
    print_json(inspect_runtime().to_dict())
    return 0


def _handle_studio(args: argparse.Namespace) -> int:
    data = RuntimeCLI().studio(
        message=args.message,
        conversation_id=args.conversation_id,
        memory_path=args.memory,
        format=args.format,
    )
    _write_or_print(data, output=args.output)
    return 0


def _handle_session_save(args: argparse.Namespace) -> int:
    _write_or_print(
        RuntimeCLI().save_session(
            message=args.message,
            conversation_id=args.conversation_id,
            memory_path=args.memory,
            output=args.output,
        )
    )
    return 0


def _handle_session_show(args: argparse.Namespace) -> int:
    _write_or_print(RuntimeCLI().show_session(path=args.path, summary=args.summary))
    return 0


def _handle_session_replay(args: argparse.Namespace) -> int:
    _write_or_print(RuntimeCLI().replay_session(path=args.path, memory_path=args.memory))
    return 0


def _handle_session_compare(args: argparse.Namespace) -> int:
    _write_or_print(RuntimeCLI().compare_sessions(left=args.left, right=args.right))
    return 0


def _handle_benchmark(args: argparse.Namespace) -> int:
    result = run_cognitive_conversation_benchmark(
        path=args.input,
        scenario_ids=args.scenario or None,
        max_scenarios=args.max_scenarios,
    )
    if args.format == "markdown":
        _write_or_print(render_cognitive_benchmark_report(result), output=args.output)
        return 0
    if args.format == "json":
        _write_or_print(json.dumps(result, ensure_ascii=False, indent=2), output=args.output)
        return 0
    _write_or_print(result, output=args.output)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ACA Runtime CLI")
    subparsers = parser.add_subparsers(dest="command")

    doctor_parser = subparsers.add_parser("doctor", help="Validate the local ACA project.")
    doctor_parser.set_defaults(handler=lambda _args: print_json(run_doctor().to_dict()) or 0)

    version_parser = subparsers.add_parser("version", help="Print ACA project version metadata.")
    version_parser.set_defaults(handler=lambda _args: print_json(read_project_version().to_dict()) or 0)

    status_parser = subparsers.add_parser("status", help="Show Runtime health summary.")
    status_parser.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    status_parser.set_defaults(handler=_handle_status)

    components_parser = subparsers.add_parser("components", help="List registered Runtime components.")
    components_sub = components_parser.add_subparsers(dest="components_command", required=True)
    components_list = components_sub.add_parser("list", help="List registered components.")
    components_list.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    _format_arg(components_list)
    components_list.set_defaults(handler=_handle_components)

    plugins_parser = subparsers.add_parser("plugins", help="List or load Plugin SDK manifests.")
    plugins_sub = plugins_parser.add_subparsers(dest="plugins_command", required=True)
    plugins_list = plugins_sub.add_parser("list", help="List loaded plugins.")
    plugins_list.add_argument("--root", default=None, help="Optional plugin root to load before listing.")
    plugins_list.add_argument("--strict", action="store_true", help="Fail on first plugin load error.")
    plugins_list.add_argument("--memory", default=None, help="Optional JSON memory file path.")
    _format_arg(plugins_list)
    plugins_list.set_defaults(handler=_handle_plugins)

    run_parser = subparsers.add_parser("run", help="Execute a simple Runtime flow.")
    _message_args(run_parser)
    run_parser.add_argument("--events", action="store_true", help="Include internal runtime events.")
    run_parser.add_argument("--trace", action="store_true", help="Include execution trace in output.")
    run_parser.add_argument("--introspection", action="store_true", help="Include runtime introspection snapshot.")
    run_parser.add_argument("--studio", action="store_true", help="Include ACA Studio view.")
    run_parser.add_argument("--save-session", default=None, help="Optional path to persist the execution session.")
    run_parser.set_defaults(handler=_handle_run)

    metrics_parser = subparsers.add_parser("metrics", help="Show Runtime metrics.")
    _message_args(metrics_parser, required=False)
    _format_arg(metrics_parser)
    metrics_parser.set_defaults(handler=_handle_metrics)

    trace_parser = subparsers.add_parser("trace", help="Run a message and print its execution trace.")
    trace_parser.add_argument("mode", nargs="?", default="last", choices=["last", "export"], help="Trace action.")
    _message_args(trace_parser)
    _format_arg(trace_parser)
    trace_parser.set_defaults(handler=_handle_trace)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect ACA Runtime data.")
    inspect_subparsers = inspect_parser.add_subparsers(dest="inspect_target", required=True)
    inspect_runtime_parser = inspect_subparsers.add_parser("runtime", help="Inspect the static runtime pipeline.")
    inspect_runtime_parser.set_defaults(handler=_handle_inspect_runtime)
    inspect_session_parser = inspect_subparsers.add_parser("session", help="Run a message and inspect runtime snapshot.")
    _message_args(inspect_session_parser)
    inspect_session_parser.set_defaults(handler=_handle_inspect_session)

    studio_parser = subparsers.add_parser("studio", help="Run a message and export the ACA Studio view.")
    _message_args(studio_parser)
    _format_arg(studio_parser, values=("dict", "json", "html"), default="dict")
    studio_parser.add_argument("--output", default=None, help="Optional file path for Studio export.")
    studio_parser.set_defaults(handler=_handle_studio)

    session_parser = subparsers.add_parser("session", help="Persist, replay and compare execution sessions.")
    session_subparsers = session_parser.add_subparsers(dest="session_command", required=True)

    session_save = session_subparsers.add_parser("save", help="Run a message and save its execution session.")
    _message_args(session_save)
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

    benchmark_parser = subparsers.add_parser(
        "benchmark",
        help="Run the cognitive conversation benchmark against the real Runtime.",
    )
    benchmark_parser.add_argument("--input", default=None, help="Optional benchmark JSON path.")
    benchmark_parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario id to run. Can be provided multiple times.",
    )
    benchmark_parser.add_argument("--max-scenarios", type=int, default=None, help="Run only the first N scenarios.")
    benchmark_parser.add_argument("--output", default=None, help="Optional report output path.")
    _format_arg(benchmark_parser, values=("dict", "json", "markdown"), default="dict")
    benchmark_parser.set_defaults(handler=_handle_benchmark)

    _message_args(parser, required=False)
    parser.add_argument("--events", action="store_true", help="Include internal runtime events.")
    parser.add_argument("--trace", action="store_true", help="Include execution trace in output.")
    parser.add_argument("--introspection", action="store_true", help="Include runtime introspection snapshot.")
    parser.add_argument("--studio", action="store_true", help="Include ACA Studio view.")
    parser.add_argument("--save-session", default=None, help="Optional path to persist the execution session.")
    parser.set_defaults(handler=_handle_run)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None and not args.message:
        parser.error("the following arguments are required: --message")
    raise SystemExit(args.handler(args))


if __name__ == "__main__":
    main()
