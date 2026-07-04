from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict

from aca_kernel.core.events import Event
from aca_os.session import ExecutionSession
from sdk.factory import build_galicia_runtime, process_message


RuntimeFactory = Callable[..., Any]


@dataclass(frozen=True)
class CLICommandResult:
    """Stable command result for thin CLI adapters."""

    payload: Dict[str, Any] | str
    format: str = "dict"

    def render(self) -> str:
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload, ensure_ascii=False, indent=2)


class RuntimeCLI:
    """Stable Runtime-backed command facade for external CLI adapters.

    The command-line script only parses arguments and prints this facade output.
    RuntimeCLI owns no business behavior: it delegates execution, traces,
    metrics, components, plugins and sessions to the Runtime API boundary.
    """

    def __init__(self, runtime_factory: RuntimeFactory = build_galicia_runtime) -> None:
        self.runtime_factory = runtime_factory

    def status(self, *, memory_path: str | Path | None = None) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        snapshot = runtime.inspect_runtime().to_dict()
        return {
            "status": snapshot["status"],
            "runtime_id": snapshot["runtime_id"],
            "component_count": len(snapshot["components"]),
            "plugin_count": runtime.export_plugins(format="dict")["plugin_count"],
            "trace_count": snapshot["metrics"]["trace_count"],
        }

    def components(self, *, format: str = "dict", memory_path: str | Path | None = None) -> Dict[str, Any] | str:
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.export_components(format=format)

    def plugins(
        self,
        *,
        root: str | Path | None = None,
        strict: bool = False,
        format: str = "dict",
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any] | str:
        runtime = self.runtime_factory(memory_path=memory_path)
        if root is not None:
            runtime.load_plugins(str(root), strict=strict)
        return runtime.export_plugins(format=format)

    def metrics(
        self,
        *,
        message: str | None = None,
        conversation_id: str = "cli",
        memory_path: str | Path | None = None,
        format: str = "dict",
    ) -> Dict[str, Any] | str:
        runtime = self.runtime_factory(memory_path=memory_path)
        if message:
            runtime.process_output(_message_event(message, conversation_id))
        return runtime.export_metrics(format=format)

    def run(
        self,
        *,
        message: str,
        conversation_id: str = "cli",
        memory_path: str | Path | None = None,
        include_events: bool = False,
        include_trace: bool = False,
        include_introspection: bool = False,
        include_studio: bool = False,
        save_session_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        result = process_message(
            message=message,
            conversation_id=conversation_id,
            memory_path=memory_path,
            include_runtime_events=include_events,
            include_introspection=include_introspection,
            include_studio=include_studio,
            save_session_path=save_session_path,
        )
        if not include_trace:
            result.pop("execution_trace", None)
        return result

    def trace(
        self,
        *,
        message: str,
        conversation_id: str = "cli",
        memory_path: str | Path | None = None,
        format: str = "dict",
    ) -> Dict[str, Any] | str:
        runtime = self.runtime_factory(memory_path=memory_path)
        runtime.process_output(_message_event(message, conversation_id))
        return runtime.export_trace(format=format)

    def introspection(
        self,
        *,
        message: str | None = None,
        conversation_id: str = "cli",
        memory_path: str | Path | None = None,
        format: str = "dict",
    ) -> Dict[str, Any] | str:
        runtime = self.runtime_factory(memory_path=memory_path)
        if message:
            runtime.process_output(_message_event(message, conversation_id))
        return runtime.export_introspection(format=format)

    def studio(
        self,
        *,
        message: str,
        conversation_id: str = "cli",
        memory_path: str | Path | None = None,
        format: str = "dict",
    ) -> Dict[str, Any] | str:
        runtime = self.runtime_factory(memory_path=memory_path)
        runtime.process_output(_message_event(message, conversation_id))
        return runtime.export_studio(format=format)

    def save_session(
        self,
        *,
        message: str,
        output: str | Path,
        conversation_id: str = "cli",
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        runtime.process_output(_message_event(message, conversation_id))
        path = runtime.save_last_session(str(output))
        session = runtime.last_session()
        return {"status": "written", "path": path, "session": session.summary() if session else {}}

    def show_session(self, *, path: str | Path, summary: bool = False) -> Dict[str, Any]:
        session = ExecutionSession.load(path)
        return session.summary() if summary else session.to_dict()

    def replay_session(
        self,
        *,
        path: str | Path,
        memory_path: str | Path | None = None,
    ) -> Dict[str, Any]:
        runtime = self.runtime_factory(memory_path=memory_path)
        return runtime.replay_session(str(path)).to_dict()

    def compare_sessions(self, *, left: str | Path, right: str | Path) -> Dict[str, Any]:
        runtime = self.runtime_factory()
        return runtime.compare_sessions(str(left), str(right))


def _message_event(message: str, conversation_id: str) -> Event:
    return Event(
        type="user_message",
        payload=message,
        metadata={"conversation_id": conversation_id},
    )
