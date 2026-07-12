from copy import deepcopy
from typing import Any, Dict
from uuid import uuid4
from time import perf_counter

from aca_kernel.core.state import CognitiveState
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.compiler.compiler import GraphCompiler
from aca_os.context_manager import ContextManager
from aca_os.conversation_state import ConversationState
from aca_os.conversation_manager import ConversationManager
from aca_os.event_bus import EventBus
from aca_os.introspection import RuntimeIntrospectionAPI, RuntimeIntrospectionSnapshot
from aca_os.execution_trace import ExecutionTrace, monotonic_ms, utc_now_iso
from aca_os.execution_authority import record_execution_authority
from aca_os.legacy_runtime_executor import LegacyRuntimeExecutor
from aca_os.memory_engine import MemoryEngine
from aca_os.metrics_engine import MetricsEngine
from aca_os.component_registry import ComponentRegistry, build_registry_from_runtime
from aca_os.plugin_lifecycle import PluginLifecycleManager
from aca_os.plugin_loader import PluginLoader
from aca_os.domain_pack_loader import DomainPackLoader
from aca_os.domain_pack_validator import DomainPackValidator
from aca_os.domain_pack_runtime import DomainPackRuntime
from aca_os.plugin_validator import PluginValidator
from aca_os.mission_manager import MissionManager
from aca_os.output import ACAOutput
from aca_os.runtime_executor import RuntimeExecutor, compare_runtime_executions
from aca_os.session import ExecutionSession
from aca_os.policy_manager import PolicyDecision, PolicyManager, PolicyResult
from aca_os.step_handlers import (
    StepExecutionContext,
    StepHandlerRegistry,
    StepRuntimeServices,
    build_default_step_handler_registry,
    plan_has_step,
    step_from_plan,
)
from aca_os.studio import build_studio_view, export_studio_view
from aca_os.tool_engine import ToolEngine, ToolExecutionMode
from zero_cost.action_planner import ActionPlanner
from zero_cost.execution_plan import ExecutionPlan
from zero_cost.flow_router import FlowRouter
from zero_cost.intent_matcher import IntentMatch, IntentMatcher
from zero_cost.decision_graph import DecisionGraphEngine


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
        decision_graph_engine: DecisionGraphEngine | None = None,
        metrics_engine: MetricsEngine | None = None,
        component_registry: ComponentRegistry | None = None,
        plugin_loader: PluginLoader | None = None,
        plugin_validator: PluginValidator | None = None,
        plugin_lifecycle: PluginLifecycleManager | None = None,
        domain_pack_loader: DomainPackLoader | None = None,
        domain_pack_validator: DomainPackValidator | None = None,
        event_bus: EventBus | None = None,
        step_handler_registry: StepHandlerRegistry | None = None,
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
        self.decision_graph_engine = decision_graph_engine or DecisionGraphEngine()
        self.metrics_engine = metrics_engine or MetricsEngine()
        self.event_bus = event_bus or EventBus()
        self.plugin_validator = plugin_validator or PluginValidator()
        self.plugin_loader = plugin_loader or PluginLoader(plugin_validator=self.plugin_validator)
        self.plugin_lifecycle = plugin_lifecycle
        self.domain_pack_validator = domain_pack_validator or DomainPackValidator()
        self.domain_pack_loader = domain_pack_loader or DomainPackLoader(validator=self.domain_pack_validator)
        self.domain_pack_runtime = DomainPackRuntime(self.domain_pack_loader)
        self.component_registry = component_registry or build_registry_from_runtime(self)
        self.plugin_validator.bind_registry(self.component_registry)
        self.plugin_loader.bind_registry(self.component_registry)
        self.domain_pack_loader.bind_registry(self.component_registry)
        if self.plugin_lifecycle is None:
            self.plugin_lifecycle = PluginLifecycleManager(
                component_registry=self.component_registry,
                plugin_loader=self.plugin_loader,
            )
        else:
            self.plugin_lifecycle.bind_registry(self.component_registry)
            self.plugin_lifecycle.bind_loader(self.plugin_loader)
        if self.component_registry.get("plugin_lifecycle") is None:
            self.component_registry.register_instance(
                name="plugin_lifecycle",
                instance=self.plugin_lifecycle,
                role="plugin lifecycle manager",
                capabilities=(
                    "plugin.initialize",
                    "plugin.activate",
                    "plugin.pause",
                    "plugin.stop",
                    "plugin.unload",
                    "plugin.lifecycle.export",
                ),
                tags=("plugin-sdk", "runtime", "governance"),
                metadata={"runtime_owned": True},
            )
            self.component_registry.initialize("plugin_lifecycle")
            self.component_registry.activate("plugin_lifecycle")
        if self.component_registry.get("domain_pack_validator") is None:
            self.component_registry.register_instance(
                name="domain_pack_validator",
                instance=self.domain_pack_validator,
                role="domain pack validator",
                capabilities=("domain_pack.validate", "domain_pack.validator.export"),
                tags=("domain-pack", "runtime", "validator"),
                metadata={"runtime_owned": True},
            )
            self.component_registry.initialize("domain_pack_validator")
            self.component_registry.activate("domain_pack_validator")
        if self.component_registry.get("domain_pack_loader") is None:
            self.component_registry.register_instance(
                name="domain_pack_loader",
                instance=self.domain_pack_loader,
                role="domain pack loader",
                capabilities=("domain_pack.discover", "domain_pack.load", "domain_pack.export"),
                tags=("domain-pack", "runtime", "loader"),
                metadata={"runtime_owned": True},
            )
            self.component_registry.initialize("domain_pack_loader")
            self.component_registry.activate("domain_pack_loader")
        if self.component_registry.get("domain_pack_runtime") is None:
            self.component_registry.register_instance(
                name="domain_pack_runtime",
                instance=self.domain_pack_runtime,
                role="domain pack runtime integration",
                capabilities=(
                    "domain_pack.runtime.load",
                    "domain_pack.runtime.export",
                    "domain_pack.runtime.context",
                ),
                tags=("domain-pack", "runtime", "integration"),
                metadata={"runtime_owned": True},
            )
            self.component_registry.initialize("domain_pack_runtime")
            self.component_registry.activate("domain_pack_runtime")
        self.domain_context = domain_context or {}
        self.domain_context.setdefault("domain_packs", self.domain_pack_runtime.context())
        self.step_services = StepRuntimeServices(
            policy_manager=self.policy_manager,
            tool_engine=self.tool_engine,
            compiler=self.compiler,
            kernel=self.kernel,
            mission_manager=self.mission_manager,
            memory_engine=self.memory_engine,
            context_manager=self.context_manager,
        )
        self.step_handlers = step_handler_registry or build_default_step_handler_registry()
        self.legacy_runtime = LegacyRuntimeExecutor(
            handlers=self.step_handlers,
            services=self.step_services,
            conversation_manager=self.conversation_manager,
            domain_context=self.domain_context,
            emit=self._emit,
        )
        self.runtime_id = str(uuid4())
        self._last_trace: ExecutionTrace | None = None
        self._traces: Dict[str, ExecutionTrace] = {}
        self._last_state: CognitiveState | None = None
        self._last_event: Event | None = None
        self._last_output: ACAOutput | None = None
        self._last_session: ExecutionSession | None = None
        self.introspection = RuntimeIntrospectionAPI(self)

    def _emit(self, event_type: str, **payload: Any) -> None:
        self.event_bus.publish(event_type, payload, source="aca_os.runtime")

    def _services_with_memory(self, memory_engine: MemoryEngine) -> StepRuntimeServices:
        return StepRuntimeServices(
            policy_manager=self.policy_manager,
            tool_engine=self.tool_engine,
            compiler=self.compiler,
            kernel=self.kernel,
            mission_manager=self.mission_manager,
            memory_engine=memory_engine,
            context_manager=self.context_manager,
        )

    def _apply_execution_step_outcomes(
        self,
        state: CognitiveState,
        step_outcomes: list[Dict[str, Any]],
    ) -> CognitiveState:
        facts = dict(state.facts)
        facts["execution_step_outcomes"] = list(step_outcomes)
        with_outcomes = state.evolve("EXECUTION_STEP_OUTCOMES", facts=facts)
        return self.conversation_manager.after_process(with_outcomes)

    def _attach_conversation_state_runtime_record(self, state: CognitiveState) -> CognitiveState:
        record = self.conversation_manager.conversation_state_runtime_record(state.conversation_id)
        facts = dict(state.facts)
        facts["conversation_state_runtime"] = record
        updated = state.evolve("CONVERSATION_STATE_RUNTIME", facts=facts)
        return self.conversation_manager.after_process(updated)

    def _execute_runtime_executor_official(
        self,
        *,
        event: Event,
        prepared: CognitiveState,
        execution_plan: ExecutionPlan,
        policy_result: PolicyResult,
        policy_outcome: Dict[str, Any] | None,
        tool_evidence: Dict[str, Any],
        conversation_state: ConversationState,
        intent_match: Any,
        action_plan: Any,
        execution_flow: Any,
    ) -> CognitiveState:
        legacy_memory = _clone_memory_engine(self.memory_engine)
        graph = None
        selected_program = None
        runtime_context: Dict[str, Any] = {
            "intent_match": intent_match.to_dict(),
            "action_plan": action_plan.to_dict(),
            "execution_flow": execution_flow.to_dict(),
            "execution_plan": execution_plan.to_dict(),
            "policy_result": policy_result.to_dict(),
            "tool_evidence": tool_evidence,
            "conversation_state": conversation_state.to_dict(),
        }
        if policy_result.decision != PolicyDecision.ESCALATE:
            graph = self.compiler.compile(event, prepared)
            selected_program = graph.name
            runtime_context["graph"] = graph
        authorized = record_execution_authority(
            prepared,
            execution_plan=execution_plan,
            selected_program=selected_program,
            executor="runtime_executor",
            policy_result=policy_result,
            emit=self._emit,
        )
        runtime_context["execution_authority"] = authorized.facts.get("runtime_execution_authority", {})
        executor_result = RuntimeExecutor(
            handlers=self.step_handlers,
            services=self.step_services,
            domain_context=self.domain_context,
        ).execute(
            event=event,
            state=authorized,
            execution_plan=execution_plan,
            initial_policy_result=policy_result,
            initial_tool_evidence=tool_evidence,
            initial_runtime_context=runtime_context,
            conversation_state=conversation_state,
            execution_mode=ToolExecutionMode.OFFICIAL,
        )
        official_state = self._apply_execution_step_outcomes(
            executor_result.final_state or authorized,
            executor_result.outcomes,
        )
        legacy_projection = self.legacy_runtime.with_services(
            self._services_with_memory(legacy_memory)
        ).project(
            event=event,
            prepared=prepared,
            execution_plan=execution_plan,
            policy_result=policy_result,
            policy_outcome=policy_outcome,
            tool_evidence=executor_result.tool_evidence or tool_evidence,
            conversation_state=conversation_state,
            intent_match=intent_match,
            action_plan=action_plan,
            execution_flow=execution_flow,
        )
        comparison = compare_runtime_executions(
            official_state=official_state,
            shadow_result=legacy_projection,
            official_engine="runtime_executor",
            shadow_engine="legacy_runtime_validation",
        )
        facts = dict(official_state.facts)
        facts["runtime_executor_shadow"] = comparison.to_dict()
        facts["runtime_executor_adoption"] = {
            "contract": "runtime_executor_controlled_adoption.v1",
            "slice": _adoption_slice_for_flow(execution_plan.flow),
            "migrated_flows": _runtime_executor_official_flows(),
            "flow": execution_plan.flow,
            "kernel_program": execution_plan.kernel_program,
        }
        facts["runtime_execution_engine"] = self._runtime_execution_engine_record(
            execution_plan=execution_plan,
            official_engine="runtime_executor",
            validation_engine="legacy_runtime_validation",
            selection_reason=f"migrated_flow_{_adoption_slice_for_flow(execution_plan.flow)}",
            comparison=comparison.to_dict(),
        )
        updated = official_state.evolve("RUNTIME_EXECUTOR_ADOPTION", facts=facts)
        self._emit(
            "runtime.executor_adoption_compared",
            runtime_execution_engine=facts["runtime_execution_engine"],
            runtime_executor_shadow=comparison.to_dict(),
        )
        return self.conversation_manager.after_process(updated)

    def _record_runtime_executor_shadow(
        self,
        official_state: CognitiveState,
        *,
        event: Event,
        shadow_start_state: CognitiveState,
        execution_plan: ExecutionPlan,
        conversation_state: ConversationState,
    ) -> CognitiveState:
        shadow_services = self._services_with_memory(_clone_memory_engine(self.memory_engine))
        shadow = RuntimeExecutor(
            handlers=self.step_handlers,
            services=shadow_services,
            domain_context=self.domain_context,
        ).execute(
            event=event,
            state=shadow_start_state,
            execution_plan=execution_plan,
            initial_tool_evidence=official_state.tool_evidence,
            conversation_state=conversation_state,
            execution_mode=ToolExecutionMode.SHADOW,
        )
        comparison = compare_runtime_executions(
            official_state=official_state,
            shadow_result=shadow,
            official_engine="legacy_runtime",
            shadow_engine="runtime_executor_shadow",
        )
        facts = dict(official_state.facts)
        facts["runtime_executor_shadow"] = comparison.to_dict()
        facts["runtime_execution_engine"] = self._runtime_execution_engine_record(
            execution_plan=execution_plan,
            official_engine="legacy_runtime",
            validation_engine="runtime_executor_shadow",
            selection_reason="flow_not_migrated",
            comparison=comparison.to_dict(),
        )
        updated = official_state.evolve("RUNTIME_EXECUTOR_SHADOW", facts=facts)
        self._emit(
            "runtime.executor_shadow_compared",
            runtime_execution_engine=facts["runtime_execution_engine"],
            runtime_executor_shadow=comparison.to_dict(),
        )
        return self.conversation_manager.after_process(updated)

    def _runtime_execution_engine_record(
        self,
        *,
        execution_plan: ExecutionPlan,
        official_engine: str,
        validation_engine: str,
        selection_reason: str,
        comparison: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "contract": "runtime_execution_engine.v1",
            "official_engine": official_engine,
            "validation_engine": validation_engine,
            "selection_reason": selection_reason,
            "flow": execution_plan.flow,
            "kernel_program": execution_plan.kernel_program,
            "tool_executions": _tool_executions_from_comparison(comparison),
            "interruption": _interruption_from_comparison(comparison, official_engine=official_engine),
            "comparison": {
                "available": True,
                "equivalent": bool(comparison.get("equivalent")),
                "equivalence_score": comparison.get("equivalence_score"),
                "equivalence_percentage": round(float(comparison.get("equivalence_score") or 0.0) * 100, 2),
                "divergence_count": len(comparison.get("divergences", [])),
                "divergences": [dict(divergence) for divergence in comparison.get("divergences", [])],
            },
        }

    def process(self, event: Event, state: CognitiveState | None = None) -> CognitiveState:
        started_perf = perf_counter()
        started_at = utc_now_iso()
        trace_id = str(uuid4())
        self._emit("runtime.process.started", trace_id=trace_id, input_event_type=event.type)
        turn_context = self.conversation_manager.begin_turn(event, state)
        conversation_state = turn_context.cognitive_state
        operational_conversation_state = turn_context.conversation_state
        intent_match = self.intent_matcher.match(event.payload)
        if turn_context.slot_resolutions:
            intent_match = _intent_from_slot_resolution(
                intent_match,
                turn_context.slot_resolutions,
                operational_conversation_state,
            )
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

        decision_graph = self.decision_graph_engine.build(
            intent_match=intent_match,
            action_plan=action_plan,
            execution_flow=execution_flow,
            execution_plan=execution_plan,
        )
        facts = dict(with_execution_plan.facts)
        facts["zero_cost_decision_graph"] = decision_graph.to_dict()
        with_decision_graph = with_execution_plan.evolve("DECISION_GRAPH", facts=facts)
        self._emit("runtime.decision_graph_created", decision_graph=decision_graph.to_dict())

        prepared = self.mission_manager.before_kernel(
            event,
            with_decision_graph,
            conversation_state=operational_conversation_state,
        )
        operational_conversation_state = self.conversation_manager.project_from_cognitive_state(
            prepared,
            source="runtime.prepared_state",
        )
        policy_execution = self.step_handlers.resolve("policy").execute(
            StepExecutionContext(
                state=prepared,
                event=event,
                execution_plan=execution_plan,
                step=step_from_plan(execution_plan, "policy"),
                services=self.step_services,
                conversation_state=operational_conversation_state,
                domain_context=self.domain_context,
            )
        )
        policy_result = policy_execution.policy_result or PolicyResult(decision=PolicyDecision.ALLOW, reason="missing_policy_result")
        policy_outcome = policy_execution.outcome if plan_has_step(execution_plan, "policy") else None
        self._emit("runtime.policy_evaluated", policy_result=policy_result.to_dict())

        if _uses_runtime_executor_officially(execution_plan):
            final_state = self._execute_runtime_executor_official(
                event=event,
                prepared=prepared,
                execution_plan=execution_plan,
                policy_result=policy_result,
                policy_outcome=policy_outcome,
                tool_evidence={},
                conversation_state=operational_conversation_state,
                intent_match=intent_match,
                action_plan=action_plan,
                execution_flow=execution_flow,
            )
            final_state = self._attach_conversation_state_runtime_record(final_state)
            self._emit("runtime.process.completed", trace_id=trace_id, final_version=final_state.version)
            self._record_trace(final_state, trace_id, started_at, started_perf, event)
            return final_state

        legacy_result = self.legacy_runtime.execute(
            event=event,
            prepared=prepared,
            execution_plan=execution_plan,
            policy_result=policy_result,
            policy_outcome=policy_outcome,
            tool_evidence={},
            conversation_state=operational_conversation_state,
            intent_match=intent_match,
            action_plan=action_plan,
            execution_flow=execution_flow,
        )
        final_state = legacy_result.final_state or prepared
        final_state = self._record_runtime_executor_shadow(
            final_state,
            event=event,
            shadow_start_state=prepared,
            execution_plan=execution_plan,
            conversation_state=operational_conversation_state,
        )
        final_state = self._attach_conversation_state_runtime_record(final_state)
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
        self.metrics_engine.observe_trace(trace)
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


    def export_metrics(self, *, format: str = "dict") -> Dict[str, Any] | str:
        return self.metrics_engine.export(runtime_id=self.runtime_id, format=format)

    def export_components(self, *, format: str = "dict") -> Dict[str, Any] | str:
        return self.component_registry.export(format=format)

    def validate_plugin(self, source: Any, *, format: str = "dict") -> Dict[str, Any] | str:
        return self.plugin_validator.export_report(source, registry=self.component_registry, format=format)

    def load_plugins(self, root: str, *, strict: bool = False) -> Dict[str, Any]:
        return self.plugin_lifecycle.load_plugins(root, strict=strict)

    def initialize_plugin(self, plugin_name: str) -> Dict[str, Any]:
        return self.plugin_lifecycle.initialize(plugin_name).to_dict()

    def activate_plugin(self, plugin_name: str) -> Dict[str, Any]:
        return self.plugin_lifecycle.activate(plugin_name).to_dict()

    def pause_plugin(self, plugin_name: str) -> Dict[str, Any]:
        return self.plugin_lifecycle.pause(plugin_name).to_dict()

    def stop_plugin(self, plugin_name: str) -> Dict[str, Any]:
        return self.plugin_lifecycle.stop(plugin_name).to_dict()

    def unload_plugin(self, plugin_name: str) -> Dict[str, Any]:
        return self.plugin_lifecycle.unload(plugin_name).to_dict()

    def export_plugins(self, *, format: str = "dict") -> Dict[str, Any] | str:
        snapshot = self.plugin_loader.export(format="dict")
        snapshot["lifecycle"] = self.plugin_lifecycle.export(format="dict")
        if format == "dict":
            return snapshot
        if format == "json":
            import json

            return json.dumps(snapshot, ensure_ascii=False, indent=2)
        raise ValueError(f"Unsupported plugin export format: {format}")

    def export_plugin_lifecycle(self, *, format: str = "dict") -> Dict[str, Any] | str:
        return self.plugin_lifecycle.export(format=format)

    def load_domain_packs(self, root: str, *, strict: bool = False) -> Dict[str, Any]:
        snapshot = self.domain_pack_runtime.load(root, strict=strict)
        self.domain_context["domain_packs"] = snapshot.to_context()
        return snapshot.to_dict()

    def export_domain_packs(self, *, format: str = "dict") -> Dict[str, Any] | str:
        return self.domain_pack_runtime.export(format=format)

    def export_domain_pack_context(self, *, format: str = "dict") -> Dict[str, Any] | str:
        context = self.domain_pack_runtime.context()
        if format == "dict":
            return context
        if format == "json":
            import json

            return json.dumps(context, ensure_ascii=False, indent=2)
        raise ValueError(f"Unsupported Domain Pack context export format: {format}")

    def get_domain_pack(self, name: str) -> Dict[str, Any]:
        return {"pack": self.domain_pack_runtime.get(name).to_dict()}

    def export_domain_pack_validation(self, *, format: str = "dict") -> Dict[str, Any] | str:
        return self.domain_pack_validator.export(format=format)

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


def _uses_runtime_executor_officially(execution_plan: ExecutionPlan) -> bool:
    return execution_plan.flow in _runtime_executor_official_flows()


def _intent_from_slot_resolution(
    original: IntentMatch,
    slot_resolutions: tuple[Dict[str, Any], ...],
    conversation_state: ConversationState,
) -> IntentMatch:
    actionable = [
        resolution
        for resolution in slot_resolutions
        if not resolution.get("repeated")
    ]
    if not actionable and (conversation_state.active_mission or {}).get("missing"):
        actionable = list(slot_resolutions)
    if not actionable:
        return original
    mission_type = (conversation_state.active_mission or {}).get("type")
    if mission_type == "auto_claim_guidance":
        confidence = max(float(resolution.get("confidence") or 0.0) for resolution in actionable)
        return IntentMatch(
            intent="auto_claim_guidance",
            confidence=round(max(confidence, 0.75), 2),
            matched_terms=[str(resolution.get("slot")) for resolution in actionable],
            reason="pending_question_answer",
        )
    return original


def _runtime_executor_official_flows() -> list[str]:
    return [
        "fallback",
        "guided_process",
        "human_handoff",
        "knowledge_lookup",
        "safe_escalation",
        "static_response",
    ]


def _adoption_slice_for_flow(flow: str) -> str:
    if flow in {"human_handoff", "safe_escalation"}:
        return "slice_4"
    if flow == "knowledge_lookup":
        return "slice_3"
    if flow == "guided_process":
        return "slice_2"
    return "slice_1"


def _tool_executions_from_comparison(comparison: Dict[str, Any]) -> list[Dict[str, Any]]:
    executions = []
    official = comparison.get("official", {})
    if not isinstance(official, dict):
        return executions
    for outcome in official.get("outcomes", []):
        if not isinstance(outcome, dict):
            continue
        result = outcome.get("result", {})
        if not isinstance(result, dict):
            continue
        execution = result.get("tool_execution")
        if isinstance(execution, dict) and execution:
            executions.append(dict(execution))
    return executions


def _interruption_from_comparison(comparison: Dict[str, Any], *, official_engine: str) -> Dict[str, Any]:
    official = comparison.get("official", {})
    if not isinstance(official, dict):
        return {"present": False}

    outcomes = official.get("outcomes", [])
    if not isinstance(outcomes, list):
        return {"present": False}

    policy_outcome = _first_outcome(outcomes, "policy")
    interruption_outcome = _first_outcome(outcomes, "handoff") or _first_outcome(outcomes, "escalation")
    source = policy_outcome or interruption_outcome
    interruption = dict((source or {}).get("interruption") or {})
    if not interruption:
        return {"present": False}

    execution_plan = official.get("execution_plan", {})
    flow = str(execution_plan.get("flow", "")) if isinstance(execution_plan, dict) else ""
    step = str((interruption_outcome or {}).get("step") or "")
    return {
        "present": True,
        "type": flow or step,
        "step": step,
        "origin_component": str((policy_outcome or {}).get("executor") or "policy_manager"),
        "executed_by": official_engine,
        "reason": interruption.get("reason"),
        "triggered_rules": list(interruption.get("triggered_rules") or []),
        "result": dict((interruption_outcome or {}).get("result") or {}),
    }


def _first_outcome(outcomes: list[Any], step_name: str) -> Dict[str, Any] | None:
    for outcome in outcomes:
        if isinstance(outcome, dict) and outcome.get("step") == step_name:
            return outcome
    return None


def _clone_memory_engine(memory_engine: MemoryEngine) -> MemoryEngine:
    clone = MemoryEngine()
    clone.working = deepcopy(memory_engine.working)
    clone.episodic = deepcopy(memory_engine.episodic)
    clone.semantic = deepcopy(memory_engine.semantic)
    clone.procedural = deepcopy(memory_engine.procedural)
    return clone
