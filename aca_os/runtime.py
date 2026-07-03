from typing import Any, Dict

from aca_kernel.core.state import CognitiveState
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.compiler.compiler import GraphCompiler
from aca_os.context_manager import ContextManager
from aca_os.conversation_manager import ConversationManager
from aca_os.memory_engine import MemoryEngine
from aca_os.mission_manager import MissionManager
from aca_os.policy_manager import PolicyDecision, PolicyManager, PolicyResult
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
        conversation_manager: ConversationManager | None = None,
        domain_context: Dict[str, Any] | None = None,
    ):
        self.kernel = kernel
        self.compiler = compiler
        self.mission_manager = mission_manager
        self.policy_manager = policy_manager or PolicyManager()
        self.tool_engine = tool_engine or ToolEngine()
        self.context_manager = context_manager or ContextManager()
        self.memory_engine = memory_engine or MemoryEngine()
        self.conversation_manager = conversation_manager or ConversationManager()
        self.domain_context = domain_context or {}

    def _collect_tool_evidence(self, policy_result: PolicyResult) -> Dict[str, Any]:
        if policy_result.decision != PolicyDecision.USE_TOOL:
            return {}

        if not policy_result.tool_key:
            return {}

        request = ToolRequest(
            tool_name="knowledge_base",
            intent="lookup_concept",
            payload={"key": policy_result.tool_key},
        )
        result = self.tool_engine.execute(request)
        return result.evidence if result.success else {"tool_error": result.error}

    def process(self, event: Event, state: CognitiveState | None = None) -> CognitiveState:
        conversation_state = self.conversation_manager.before_process(event, state)
        prepared = self.mission_manager.before_kernel(event, conversation_state)

        policy_result = self.policy_manager.evaluate(
            prepared,
            event,
            domain_context=self.domain_context,
        )
        tool_evidence = self._collect_tool_evidence(policy_result)

        if policy_result.decision == PolicyDecision.ESCALATE:
            prepared = prepared.evolve(
                "POLICY_ESCALATE",
                response="No tengo acceso al expediente ni puedo confirmar estados reales. Puedo orientarte con informacion general o ayudarte a hablar con una persona.",
            )

        graph = self.compiler.compile(event, prepared)
        processed = self.kernel.run(
            event,
            graph,
            prepared,
            context={
                "policy_result": policy_result.to_dict(),
                "tool_evidence": tool_evidence,
            },
        )

        mission_updated = self.mission_manager.after_kernel(processed)
        with_policy = mission_updated.evolve("POLICY_RESULT", policy_result=policy_result.to_dict())
        with_tools = with_policy.evolve("TOOL_EVIDENCE", tool_evidence=tool_evidence)

        context_bundle = self.context_manager.build(
            with_tools,
            memory=self.memory_engine.semantic,
            tool_evidence=tool_evidence,
            domain_context=self.domain_context,
        )

        final_state = with_tools.evolve("CONTEXT_BUILD", context_bundle=context_bundle.to_dict())
        return self.conversation_manager.after_process(final_state)