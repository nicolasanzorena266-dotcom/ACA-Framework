from typing import Any, Dict

from aca_kernel.core.state import CognitiveState
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.compiler.compiler import GraphCompiler
from aca_os.context_manager import ContextManager
from aca_os.memory_engine import MemoryEngine
from aca_os.mission_manager import MissionManager
from aca_os.policy_manager import PolicyDecision, PolicyManager
from aca_os.tool_engine import ToolEngine, ToolRequest


class ACAOSRuntime:
    def __init__(
        self,
        kernel: ACAKernel,
        compiler: GraphCompiler,
        mission_manager: MissionManager,
        policy_manager: PolicyManager | None = None,
        tool_engine: ToolEngine | None = None,
        context_manager: ContextManager | None = None,
        memory_engine: MemoryEngine | None = None,
        domain_context: Dict[str, Any] | None = None,
    ):
        self.kernel = kernel
        self.compiler = compiler
        self.mission_manager = mission_manager
        self.policy_manager = policy_manager or PolicyManager()
        self.tool_engine = tool_engine or ToolEngine()
        self.context_manager = context_manager or ContextManager()
        self.memory_engine = memory_engine or MemoryEngine()
        self.domain_context = domain_context or {}

    def _collect_tool_evidence(self, decision: str, event: Event) -> Dict[str, Any]:
        if decision != PolicyDecision.USE_TOOL:
            return {}

        text = str(event.payload).lower()
        if "cleas" in text or "convenio" in text:
            request = ToolRequest(
                tool_name="knowledge_base",
                intent="lookup_concept",
                payload={"key": "cleas"},
            )
            result = self.tool_engine.execute(request)
            return result.evidence if result.success else {"tool_error": result.error}

        return {}

    def process(self, event: Event, state: CognitiveState | None = None) -> CognitiveState:
        prepared = self.mission_manager.before_kernel(event, state)

        decision = self.policy_manager.evaluate(prepared, event)
        tool_evidence = self._collect_tool_evidence(decision, event)

        if decision == PolicyDecision.ESCALATE:
            prepared = prepared.evolve(
                "POLICY_ESCALATE",
                response="Puedo ayudarte a hablar con una persona para revisar esto.",
            )

        graph = self.compiler.compile(event, prepared)
        processed = self.kernel.run(
            event,
            graph,
            prepared,
            context={"policy_decision": decision, "tool_evidence": tool_evidence},
        )

        mission_updated = self.mission_manager.after_kernel(processed)
        with_tools = mission_updated.evolve("TOOL_EVIDENCE", tool_evidence=tool_evidence)

        context_bundle = self.context_manager.build(
            with_tools,
            memory=self.memory_engine.semantic,
            tool_evidence=tool_evidence,
            domain_context=self.domain_context,
        )

        return with_tools.evolve("CONTEXT_BUILD", context_bundle=context_bundle.to_dict())
