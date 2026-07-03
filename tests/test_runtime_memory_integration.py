from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.memory_engine import MemoryEngine
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime


def test_runtime_consolidates_memory_after_processing():
    memory_engine = MemoryEngine()

    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
        memory_engine=memory_engine,
    )

    state = runtime.process(Event(type="user_message", payload="Me chocaron ayer"))

    assert state.memory_snapshot["consolidated"]["last_mission_type"] == "auto_claim_guidance"
    assert state.context_bundle["relevant_memory"]["current_mission_type"] == "auto_claim_guidance"
    assert memory_engine.semantic["last_mission_type"] == "auto_claim_guidance"