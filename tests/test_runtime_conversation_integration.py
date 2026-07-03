from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.conversation_manager import ConversationManager
from aca_os.mission_manager import MissionManager
from aca_os.runtime import ACAOSRuntime


def test_runtime_tracks_conversation_session():
    conversation_manager = ConversationManager()
    runtime = ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
        conversation_manager=conversation_manager,
    )

    state = runtime.process(
        Event(
            type="user_message",
            payload="Me chocaron ayer",
            metadata={"conversation_id": "conv-runtime"},
        )
    )

    session = conversation_manager.get_session("conv-runtime")

    assert session is not None
    assert session.active_state == state
    assert len(session.turns) == 1
    assert state.active_mission["type"] == "auto_claim_guidance"