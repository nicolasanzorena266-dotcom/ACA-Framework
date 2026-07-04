from typing import Any, Dict
from uuid import uuid4
from time import perf_counter

from aca_kernel.core.state import CognitiveState
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.compiler.compiler import GraphCompiler
from aca_os.context_manager import ContextManager
from aca_os.conversation_manager import ConversationManager
from aca_os.event_bus import EventBus
from aca_os.introspection import RuntimeIntrospectionAPI, RuntimeIntrospectionSnapshot
from aca_os.execution_trace import ExecutionTrace, monotonic_ms, utc_now_iso
from aca_os.memory_engine import MemoryEngine
from aca_os.mission_manager import MissionManager
from aca_os.output import ACAOutput
from aca_os.session import ExecutionSession
from aca_os.policy_manager import PolicyDecision, PolicyManager, PolicyResult
from aca_os.studio import build_studio_view, export_studio_view
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
        self.runtime_id = str(uuid4())
        self._last_trace: ExecutionTrace | None = None
        self._traces: Dict[str, ExecutionTrace] = {}
        self._last_state: CognitiveState | None = None
        self._last_event: Event | None = None
        self._last_output: ACAOutput | None = None
        self._last_session: ExecutionSession | None = None
        self.introspection = RuntimeIntrospectionAPI(self)

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
        started_perf = perf_counter()
        started_at = utc_now_iso()
        trace_id = str(uuid4())
        self._emit("runtime.process.started", trace_id=trace_id, input_event_type=event.type)
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
            self._emit("runtime.process.completed", trace_id=trace_id, final_version=final_state.version)
            self._record_trace(final_state, trace_id, started_at, started_perf, event)
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
        self._emit("runtime.process.completed", trace_id=trace_id, final_version=final_state.version)
        self._record_trace(final_state, trace_id, started_at, started_perf, event)
        return final_state

    def _record_trace(
        self,
        state: CognitiveState,
        trace_id: str,
        started_at: str,
        started_perf: float,
        event: Event,
    ) -> ExecutionTrace:
        trace = ExecutionTrace.from_state(
            state,
            self.event_bus.events(),
            trace_id=trace_id,
            runtime_id=self.runtime_id,
            started_at=started_at,
            finished_at=utc_now_iso(),
            duration_ms=monotonic_ms(started_perf),
            metadata={
                "input_event_id": event.id,
                "input_event_type": event.type,
            },
        )
        self._last_trace = trace
        self._traces[trace.trace_id] = trace
        self._last_state = state
        self._last_event = event
        return trace

    def last_trace(self) -> ExecutionTrace | None:
        return self._last_trace

    def trace(self, trace_id: str) -> ExecutionTrace | None:
        return self._traces.get(trace_id)

    def inspect_runtime(self) -> RuntimeIntrospectionSnapshot:
        return self.introspection.snapshot(state=self._last_state)

    def export_introspection(self, *, format: str = "dict") -> Dict[str, Any] | str:
        snapshot = self.inspect_runtime().to_dict()
        if format == "json":
            import json

            return json.dumps(snapshot, ensure_ascii=False, indent=2)
        if format == "dict":
            return snapshot
        raise ValueError(f"Unsupported introspection export format: {format}")

    def export_trace(self, trace_id: str | None = None, *, format: str = "dict") -> Dict[str, Any] | str:
        trace = self._last_trace if trace_id is None else self.trace(trace_id)
        if trace is None:
            raise ValueError("No execution trace available.")
        if format == "json":
            return trace.to_json()
        if format == "dict":
            return trace.to_dict()
        raise ValueError(f"Unsupported trace export format: {format}")


    def studio_view(self):
        return build_studio_view(self.inspect_runtime())

    def export_studio(self, *, format: str = "dict") -> Dict[str, Any] | str:
        return export_studio_view(self.studio_view(), format=format)

    def process_output(self, event: Event, state: CognitiveState | None = None) -> ACAOutput:
        self.event_bus.clear()
        final_state = self.process(event, state)
        output = ACAOutput.from_state(final_state, self.event_bus.events(), self.last_trace())
        self._last_output = output
        self._last_session = ExecutionSession.from_runtime(
            runtime_id=self.runtime_id,
            event=event,
            state=final_state,
            output=output.to_dict(),
            trace=self.export_trace(),
            introspection=self.inspect_runtime().to_dict(),
        )
        return output

    def last_session(self) -> ExecutionSession | None:
        return self._last_session

    def save_last_session(self, path: str) -> str:
        if self._last_session is None:
            raise ValueError("No execution session available.")
        return str(self._last_session.save(path))

    def load_session(self, path: str) -> ExecutionSession:
        return ExecutionSession.load(path)

    def replay_session(self, session: ExecutionSession | str) -> ACAOutput:
        loaded = self.load_session(session) if isinstance(session, str) else session
        return self.process_output(loaded.replay_event())

    def compare_sessions(self, left: ExecutionSession | str, right: ExecutionSession | str) -> Dict[str, Any]:
        left_session = self.load_session(left) if isinstance(left, str) else left
        right_session = self.load_session(right) if isinstance(right, str) else right
        return left_session.compare(right_session)
