from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.memory_engine import MemoryEngine
from aca_os.memory_store import JsonMemoryStore
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime
from aca_os.tool_engine import StaticKnowledgeAdapter, ToolEngine
from domains.galicia.domain_pack import load_galicia_domain


def build_galicia_runtime(
    memory_path: str | Path | None = None,
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
        domain_context=domain.context(),
    )


def process_message(
    message: str,
    conversation_id: str = "default",
    memory_path: str | Path | None = None,
) -> Dict[str, Any]:
    runtime = build_galicia_runtime(memory_path=memory_path)

    output = runtime.process_output(
        Event(
            type="user_message",
            payload=message,
            metadata={"conversation_id": conversation_id},
        )
    )

    return output.to_dict()