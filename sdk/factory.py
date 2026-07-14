from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.event_bus import EventBus
from aca_os.memory_engine import MemoryEngine
from aca_os.memory_store import JsonMemoryStore
from aca_os.mission_manager import MissionManager
from aca_os.operational_tools import HandoffPackageAdapter
from aca_os.runtime import ACAOSRuntime
from aca_os.tool_engine import StaticKnowledgeAdapter, ToolEngine
from domains.galicia.domain_pack import load_galicia_domain


def build_galicia_runtime(
    memory_path: str | Path | None = None,
    event_bus: EventBus | None = None,
) -> ACAOSRuntime:
    domain = load_galicia_domain()

    tool_engine = ToolEngine()
    tool_engine.register(
        StaticKnowledgeAdapter(
            {
                "cleas": domain.concepts["cleas"],
                "franquicia": domain.concepts["franquicia"],
                "denuncia_administrativa": domain.concepts["denuncia_administrativa"],
            }
        )
    )
    tool_engine.register(HandoffPackageAdapter())

    memory_engine = (
        MemoryEngine(store=JsonMemoryStore(memory_path))
        if memory_path
        else MemoryEngine()
    )

    return ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
        tool_engine=tool_engine,
        memory_engine=memory_engine,
        event_bus=event_bus,
        domain_context=domain.context(),
    )


def process_message(
    message: str,
    conversation_id: str = "default",
    memory_path: str | Path | None = None,
    include_runtime_events: bool = False,
    include_introspection: bool = False,
    include_studio: bool = False,
    save_session_path: str | Path | None = None,
) -> Dict[str, Any]:
    event_bus = EventBus() if include_runtime_events else None
    runtime = build_galicia_runtime(memory_path=memory_path, event_bus=event_bus)

    output = runtime.process_output(
        Event(
            type="user_message",
            payload=message,
            metadata={"conversation_id": conversation_id},
        )
    )

    result = output.to_dict()
    if include_runtime_events and event_bus is not None:
        result["runtime_events"] = [event.to_dict() for event in event_bus.events()]
    if include_introspection:
        result["introspection"] = runtime.inspect_runtime().to_dict()
    if include_studio:
        result["studio"] = runtime.studio_view().to_dict()
    if save_session_path:
        result["session"] = runtime.last_session().summary() if runtime.last_session() else {}
        result["session_path"] = runtime.save_last_session(str(save_session_path))
    return result
