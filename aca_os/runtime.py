from typing import Any, Dict

from aca_kernel.core.state import CognitiveState
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.compiler.compiler import GraphCompiler
from aca_os.context_manager import ContextManager
from aca_os.conversation_manager import ConversationManager
from aca_os.event_bus import EventBus
from aca_os.memory_engine import MemoryEngine
from aca_os.mission_manager import MissionManager
from aca_os.output import ACAOutput
from aca_os.policy_manager import PolicyDecision, PolicyManager, PolicyResult
from aca_os.tool_engine import ToolEngine, ToolRequest
from zero_cost.action_planner import ActionPlanner
from zero_cost.execution_plan import ExecutionPlan
from zero_cost.flow_router import FlowRouter
from zero_cost.intent_matcher import IntentMatcher


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
        intent_matcher: IntentMatcher | None = None,
        action_planner: ActionPlanner | None = None,
        flow_router: FlowRouter | None = None,
        event_bus: EventBus | None = None,
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
        self.intent_matcher = intent_matcher or IntentMatcher()
        self.action_planner = action_planner or ActionPlanner()
        self.flow_router = flow_router or FlowRouter()
        self.event_bus = event_bus or EventBus()
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

    def _finalize_state(
        self,
        state: CognitiveState,
        policy_result: PolicyResult,
        tool_evidence: Dict[str, Any],
    ) -> CognitiveState:
        mission_updated = self.mission_manager.after_kernel(state)
        with_policy = mission_updated.evolve("POLICY_RESULT", policy_result=policy_result.to_dict())
        with_tools = with_policy.evolve("TOOL_EVIDENCE", tool_evidence=tool_evidence)

        consolidated_memory = self.memory_engine.consolidate(with_tools)
        relevant_memory = self.memory_engine.relevant_for_state(with_tools)

        with_memory = with_tools.evolve(
            "MEMORY_CONSOLIDATE",
            memory_snapshot={
                "consolidated": consolidated_memory,
                "relevant": relevant_memory,
            },
        )

        context_bundle = self.context_manager.build(
            with_memory,
            memory=relevant_memory,
            tool_evidence=tool_evidence,
            domain_context=self.domain_context,
        )

        final_state = with_memory.evolve("CONTEXT_BUILD", context_bundle=context_bundle.to_dict())
        return self.conversation_manager.after_process(final_state)

    def _emit(self, event_type: str, **payload: Any) -> None:
        self.event_bus.publish(event_type, payload, source="aca_os.runtime")

    def process(self, event: Event, state: CognitiveState | None = None) -> CognitiveState:
        self._emit("runtime.process.started", input_event_type=event.type)
        conversation_state = self.conversation_manager.before_process(event, state)
        intent_match = self.intent_matcher.match(event.payload)
        with_intent = conversation_state.evolve("INTENT_MATCH", intent_match=intent_match.to_dict())
        self._emit("runtime.intent_matched", intent_match=intent_match.to_dict())

        action_plan = self.action_planner.plan(intent_match)
        execution_flow = self.flow_router.route(action_plan)
        execution_plan = ExecutionPlan.from_flow(execution_flow)

        facts = dict(with_intent.facts)
        facts["zero_cost_action_plan"] = action_plan.to_dict()
        with_action_plan = with_intent.evolve("ACTION_PLAN", facts=facts)
        self._emit("runtime.action_planned", action_plan=action_plan.to_dict())

        facts = dict(with_action_plan.facts)
        facts["zero_cost_execution_flow"] = execution_flow.to_dict()
        with_execution_flow = with_action_plan.evolve("FLOW_ROUTE", facts=facts)
        self._emit("runtime.flow_routed", execution_flow=execution_flow.to_dict())

        facts = dict(with_execution_flow.facts)
        facts["zero_cost_execution_plan"] = execution_plan.to_dict()
        with_execution_plan = with_execution_flow.evolve("EXECUTION_PLAN", facts=facts)
        self._emit("runtime.execution_plan_created", execution_plan=execution_plan.to_dict())

        prepared = self.mission_manager.before_kernel(event, with_execution_plan)

        policy_result = self.policy_manager.evaluate(
            prepared,
            event,
            domain_context=self.domain_context,
        )
        tool_evidence = self._collect_tool_evidence(policy_result)
        self._emit("runtime.policy_evaluated", policy_result=policy_result.to_dict())

        if policy_result.decision == PolicyDecision.ESCALATE:
            escalated = prepared.evolve(
                "POLICY_ESCALATE",
                response="No tengo acceso al expediente ni puedo confirmar estados reales. Puedo orientarte con informacion general o ayudarte a hablar con una persona.",
            )
            final_state = self._finalize_state(escalated, policy_result, tool_evidence)
            self._emit("runtime.process.completed", final_version=final_state.version)
            return final_state

        graph = self.compiler.compile(event, prepared)
        processed = self.kernel.run(
            event,
            graph,
            prepared,
            context={
                "intent_match": intent_match.to_dict(),
                "action_plan": action_plan.to_dict(),
                "execution_flow": execution_flow.to_dict(),
                "execution_plan": execution_plan.to_dict(),
                "policy_result": policy_result.to_dict(),
                "tool_evidence": tool_evidence,
            },
        )

        final_state = self._finalize_state(processed, policy_result, tool_evidence)
        self._emit("runtime.process.completed", final_version=final_state.version)
        return final_state

    def process_output(self, event: Event, state: CognitiveState | None = None) -> ACAOutput:
        return ACAOutput.from_state(self.process(event, state))