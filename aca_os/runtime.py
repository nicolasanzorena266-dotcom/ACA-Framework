from aca_kernel.core.state import CognitiveState
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.compiler.compiler import GraphCompiler
from aca_os.mission_manager import MissionManager

class ACAOSRuntime:
    def __init__(self, kernel: ACAKernel, compiler: GraphCompiler, mission_manager: MissionManager):
        self.kernel = kernel
        self.compiler = compiler
        self.mission_manager = mission_manager

    def process(self, event: Event, state: CognitiveState | None = None) -> CognitiveState:
        prepared = self.mission_manager.before_kernel(event, state)
        graph = self.compiler.compile(event, prepared)
        processed = self.kernel.run(event, graph, prepared)
        return self.mission_manager.after_kernel(processed)
