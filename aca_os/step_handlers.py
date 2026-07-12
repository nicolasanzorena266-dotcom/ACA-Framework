from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Dict, Mapping, Protocol

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.core.state import CognitiveState
from aca_os.context_manager import ContextManager
from aca_os.conversation_state import ConversationState
from aca_os.execution_trace import monotonic_ms, utc_now_iso
from aca_os.memory_engine import MemoryEngine
from aca_os.mission_manager import MissionManager
from aca_os.policy_manager import PolicyDecision, PolicyManager, PolicyResult
from aca_os.tool_engine import ToolEngine, ToolExecutionContext, ToolExecutionMode, ToolRequest
from zero_cost.execution_plan import ExecutionPlan, ExecutionStep, ExecutionStepOutcome


@dataclass(frozen=True)
class StepRuntimeServices:
    policy_manager: PolicyManager
    tool_engine: ToolEngine
    compiler: GraphCompiler
    kernel: ACAKernel
    mission_manager: MissionManager
    memory_engine: MemoryEngine
    context_manager: ContextManager


@dataclass(frozen=True)
class StepExecutionContext:
    state: CognitiveState
    event: Event
    execution_plan: ExecutionPlan
    step: ExecutionStep
    services: StepRuntimeServices
    conversation_state: ConversationState | None = None
    domain_context: Dict[str, Any] = field(default_factory=dict)
    policy_result: PolicyResult | None = None
    tool_evidence: Dict[str, Any] = field(default_factory=dict)
    runtime_context: Dict[str, Any] = field(default_factory=dict)
    runtime_config: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StepExecutionResult:
    status: str
    outcome: Dict[str, Any]
    state: CognitiveState | None = None
    policy_result: PolicyResult | None = None
    produced_evidence: Dict[str, Any] = field(default_factory=dict)
    state_changes: Dict[str, Any] = field(default_factory=dict)
    interruption: Dict[str, Any] | None = None
    continue_execution: bool = True
    error: str | None = None
    data: Dict[str, Any] = field(default_factory=dict)


class StepHandler(Protocol):
    step_name: str

    def execute(self, context: StepExecutionContext) -> StepExecutionResult:
        ...


class StepHandlerRegistry:
    def __init__(self) -> None:
        self._handlers: Dict[str, StepHandler] = {}

    def register(self, handler: StepHandler) -> None:
        self._handlers[handler.step_name] = handler

    def resolve(self, step_name: str) -> StepHandler:
        try:
            return self._handlers[step_name]
        except KeyError as exc:
            raise KeyError(f"No StepHandler registered for step: {step_name}") from exc

    def can_handle(self, step_name: str) -> bool:
        return step_name in self._handlers

    def registered_steps(self) -> list[str]:
        return sorted(self._handlers)


class PolicyStepHandler:
    step_name = "policy"

    def execute(self, context: StepExecutionContext) -> StepExecutionResult:
        started_at = utc_now_iso()
        started_perf = perf_counter()
        result = context.services.policy_manager.evaluate(
            context.state,
            context.event,
            domain_context=context.domain_context,
        )
        interruption = None
        status = "success"
        continue_execution = True
        if result.decision == PolicyDecision.ESCALATE:
            status = "interrupted"
            continue_execution = False
            interruption = {"reason": result.reason, "triggered_rules": list(result.triggered_rules)}
        outcome = _outcome(
            step=context.step.name,
            executor="policy_manager",
            status=status,
            started_at=started_at,
            started_perf=started_perf,
            result=result.to_dict(),
            interruption=interruption,
        )
        return StepExecutionResult(
            status=status,
            outcome=outcome,
            policy_result=result,
            interruption=interruption,
            continue_execution=continue_execution,
        )


class ToolLookupStepHandler:
    step_name = "tool_lookup"

    def execute(self, context: StepExecutionContext) -> StepExecutionResult:
        started_at = utc_now_iso()
        started_perf = perf_counter()
        policy_result = context.policy_result
        evidence: Dict[str, Any] = {}
        tool_execution: Dict[str, Any] = {}
        if policy_result is None or policy_result.decision != PolicyDecision.USE_TOOL:
            status = "skipped"
        elif not policy_result.tool_key:
            status = "skipped"
        else:
            request = ToolRequest(
                tool_name="knowledge_base",
                intent="lookup_concept",
                payload={"key": policy_result.tool_key},
            )
            tool_context = ToolExecutionContext(
                mode=str(context.runtime_config.get("tool_execution_mode", ToolExecutionMode.OFFICIAL)),
                origin=str(context.runtime_config.get("origin", "tool_lookup_step_handler")),
                execution_plan=context.execution_plan.to_dict(),
                runtime_engine=str(context.runtime_config.get("runtime_engine", "legacy_runtime")),
                permissions=dict(context.runtime_config.get("tool_permissions", {})),
                simulation=dict(context.runtime_config.get("simulation", {})),
                existing_evidence=dict(context.tool_evidence),
                replay_evidence=dict(context.runtime_context.get("tool_replay_evidence", {})),
            )
            tool_result = context.services.tool_engine.execute(request, context=tool_context)
            evidence = tool_result.evidence if tool_result.success else {"tool_error": tool_result.error}
            status = "success" if tool_result.success else "error"
            tool_execution = tool_result.execution
        error = str(evidence.get("tool_error")) if "tool_error" in evidence else None
        outcome = _outcome(
            step=context.step.name,
            executor="tool_engine",
            status=status,
            started_at=started_at,
            started_perf=started_perf,
            result={
                "tool_key": policy_result.tool_key if policy_result else None,
                "tool_execution": tool_execution,
            },
            evidence=evidence,
            error=error,
        )
        return StepExecutionResult(
            status=status,
            outcome=outcome,
            produced_evidence=evidence,
            error=error,
        )


class KernelStepHandler:
    step_name = "kernel"

    def execute(self, context: StepExecutionContext) -> StepExecutionResult:
        started_at = utc_now_iso()
        started_perf = perf_counter()
        graph = context.runtime_context.get("graph")
        if graph is None:
            graph = context.services.compiler.compile(context.event, context.state)
        kernel_context = dict(context.runtime_context)
        kernel_context.pop("graph", None)
        kernel_context.setdefault("execution_plan", context.execution_plan.to_dict())
        kernel_context.setdefault("policy_result", context.policy_result.to_dict() if context.policy_result else {})
        kernel_context.setdefault("tool_evidence", context.tool_evidence)
        if context.conversation_state is not None:
            kernel_context.setdefault("conversation_state", context.conversation_state.to_dict())
        processed = context.services.kernel.run(context.event, graph, context.state, context=kernel_context)
        outcome = _outcome(
            step=context.step.name,
            executor="kernel",
            status="success",
            started_at=started_at,
            started_perf=started_perf,
            result={"selected_program": graph.name, "response": processed.response},
            state_changes={"from_version": context.state.version, "to_version": processed.version},
        )
        return StepExecutionResult(
            status="success",
            outcome=outcome,
            state=processed,
            state_changes={"from_version": context.state.version, "to_version": processed.version},
            data={"selected_program": graph.name},
        )


class HandoffStepHandler:
    step_name = "handoff"

    def execute(self, context: StepExecutionContext) -> StepExecutionResult:
        return _interruption_result(context)


class EscalationStepHandler:
    step_name = "escalation"

    def execute(self, context: StepExecutionContext) -> StepExecutionResult:
        return _interruption_result(context)


class MemoryStepHandler:
    step_name = "memory"

    def execute(self, context: StepExecutionContext) -> StepExecutionResult:
        started_at = utc_now_iso()
        started_perf = perf_counter()
        policy_result = context.policy_result or PolicyResult(decision=PolicyDecision.ALLOW, reason="missing_policy_result")
        mission_updated = context.services.mission_manager.after_kernel(
            context.state,
            conversation_state=context.conversation_state,
        )
        with_policy = mission_updated.evolve("POLICY_RESULT", policy_result=policy_result.to_dict())
        with_tools = with_policy.evolve("TOOL_EVIDENCE", tool_evidence=context.tool_evidence)
        consolidated_memory = context.services.memory_engine.consolidate(with_tools)
        relevant_memory = context.services.memory_engine.relevant_for_state(with_tools)
        with_memory = with_tools.evolve(
            "MEMORY_CONSOLIDATE",
            memory_snapshot={"consolidated": consolidated_memory, "relevant": relevant_memory},
        )
        outcome = _outcome(
            step=context.step.name,
            executor="memory_engine",
            status="success",
            started_at=started_at,
            started_perf=started_perf,
            result={"consolidated_items": len(consolidated_memory), "relevant_items": len(relevant_memory)},
            state_changes={"operation": "MEMORY_CONSOLIDATE"},
        )
        return StepExecutionResult(
            status="success",
            outcome=outcome,
            state=with_memory,
            state_changes={"operation": "MEMORY_CONSOLIDATE"},
            data={"consolidated_memory": consolidated_memory, "relevant_memory": relevant_memory},
        )


class ContextStepHandler:
    step_name = "context"

    def execute(self, context: StepExecutionContext) -> StepExecutionResult:
        started_at = utc_now_iso()
        started_perf = perf_counter()
        relevant_memory = context.runtime_context.get("relevant_memory", {})
        context_bundle = context.services.context_manager.build(
            context.state,
            memory=relevant_memory if isinstance(relevant_memory, dict) else {},
            tool_evidence=context.tool_evidence,
            domain_context=context.domain_context,
        )
        updated = context.state.evolve("CONTEXT_BUILD", context_bundle=context_bundle.to_dict())
        outcome = _outcome(
            step=context.step.name,
            executor="context_manager",
            status="success",
            started_at=started_at,
            started_perf=started_perf,
            result={"context_keys": list(context_bundle.to_dict().keys())},
            evidence={"tool_evidence_keys": list(context.tool_evidence.keys())},
            state_changes={"operation": "CONTEXT_BUILD"},
        )
        return StepExecutionResult(
            status="success",
            outcome=outcome,
            state=updated,
            state_changes={"operation": "CONTEXT_BUILD"},
            data={"context_bundle": context_bundle.to_dict()},
        )


class OutputStepHandler:
    step_name = "output"

    def execute(self, context: StepExecutionContext) -> StepExecutionResult:
        started_at = utc_now_iso()
        started_perf = perf_counter()
        outcome = _outcome(
            step=context.step.name,
            executor="runtime",
            status="success",
            started_at=started_at,
            started_perf=started_perf,
            result={"response": context.state.response},
            state_changes={"response_present": bool(context.state.response)},
        )
        return StepExecutionResult(
            status="success",
            outcome=outcome,
            state=context.state,
            state_changes={"response_present": bool(context.state.response)},
        )


def build_default_step_handler_registry() -> StepHandlerRegistry:
    registry = StepHandlerRegistry()
    for handler in (
        PolicyStepHandler(),
        ToolLookupStepHandler(),
        KernelStepHandler(),
        MemoryStepHandler(),
        ContextStepHandler(),
        OutputStepHandler(),
        HandoffStepHandler(),
        EscalationStepHandler(),
    ):
        registry.register(handler)
    return registry


def _outcome(
    *,
    step: str,
    executor: str,
    status: str,
    started_at: str,
    started_perf: float,
    result: Dict[str, Any] | None = None,
    evidence: Dict[str, Any] | None = None,
    state_changes: Dict[str, Any] | None = None,
    error: str | None = None,
    interruption: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return ExecutionStepOutcome(
        step=step,
        executor=executor,
        status=status,
        started_at=started_at,
        finished_at=utc_now_iso(),
        duration_ms=monotonic_ms(started_perf),
        result=result or {},
        evidence=evidence or {},
        state_changes=state_changes or {},
        error=error,
        interruption=interruption,
    ).to_dict()


def _interruption_result(context: StepExecutionContext) -> StepExecutionResult:
    started_at = utc_now_iso()
    started_perf = perf_counter()
    policy_result = context.policy_result or PolicyResult(decision=PolicyDecision.ESCALATE, reason="policy_interruption")
    updated = context.state.evolve(
        "POLICY_ESCALATE",
        response="No tengo acceso al expediente ni puedo confirmar estados reales. Puedo orientarte con informacion general o ayudarte a hablar con una persona.",
    )
    interruption = {"reason": policy_result.reason, "triggered_rules": list(policy_result.triggered_rules)}
    outcome = _outcome(
        step=context.step.name,
        executor="policy_manager",
        status="success",
        started_at=started_at,
        started_perf=started_perf,
        result={"response": updated.response},
        interruption=interruption,
        state_changes={"operation": "POLICY_ESCALATE"},
    )
    return StepExecutionResult(
        status="success",
        outcome=outcome,
        state=updated,
        interruption=interruption,
        continue_execution=False,
        state_changes={"operation": "POLICY_ESCALATE"},
    )


def step_from_plan(execution_plan: ExecutionPlan, step_name: str) -> ExecutionStep:
    for step in execution_plan.steps:
        if step.name == step_name:
            return step
    return ExecutionStep(name=step_name)


def plan_has_step(execution_plan: ExecutionPlan | None, step_name: str) -> bool:
    if execution_plan is None:
        return False
    return step_name in execution_plan.step_names()
