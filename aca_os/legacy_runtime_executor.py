from __future__ import annotations

from typing import Any, Callable, Dict

from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.conversation_manager import ConversationManager
from aca_os.conversation_state import ConversationState
from aca_os.execution_authority import record_execution_authority
from aca_os.policy_manager import PolicyDecision, PolicyResult
from aca_os.runtime_executor import RuntimeExecutor, RuntimeExecutorResult
from aca_os.step_handlers import (
    StepExecutionContext,
    StepHandlerRegistry,
    StepRuntimeServices,
    plan_has_step,
    step_from_plan,
)
from aca_os.tool_engine import ToolExecutionMode
from zero_cost.execution_plan import ExecutionPlan


class LegacyRuntimeExecutor:
    """Compatibility executor for pre-RuntimeExecutor orchestration.

    This component keeps the remaining imperative runtime branches isolated
    while migration continues. It should be deleted once every flow is executed
    by `RuntimeExecutor`.
    """

    def __init__(
        self,
        *,
        handlers: StepHandlerRegistry,
        services: StepRuntimeServices,
        conversation_manager: ConversationManager,
        domain_context: Dict[str, Any] | None = None,
        emit: Callable[..., None] | None = None,
    ) -> None:
        self.handlers = handlers
        self.services = services
        self.conversation_manager = conversation_manager
        self.domain_context = domain_context or {}
        self.emit = emit

    def with_services(self, services: StepRuntimeServices) -> "LegacyRuntimeExecutor":
        return LegacyRuntimeExecutor(
            handlers=self.handlers,
            services=services,
            conversation_manager=self.conversation_manager,
            domain_context=self.domain_context,
            emit=None,
        )

    def execute(
        self,
        *,
        event: Event,
        prepared: CognitiveState,
        execution_plan: ExecutionPlan,
        policy_result: PolicyResult,
        policy_outcome: Dict[str, Any] | None,
        tool_evidence: Dict[str, Any],
        intent_match: Any,
        action_plan: Any,
        execution_flow: Any,
        conversation_state: ConversationState | None = None,
    ) -> RuntimeExecutorResult:
        if policy_result.decision == PolicyDecision.ESCALATE:
            return self._execute_interruption(
                mode="legacy_runtime",
                event=event,
                prepared=prepared,
                execution_plan=execution_plan,
                policy_result=policy_result,
                policy_outcome=policy_outcome,
                tool_evidence=tool_evidence,
                conversation_state=conversation_state,
                emit_authority=True,
            )
        return self._execute_kernel_path(
            mode="legacy_runtime",
            event=event,
            prepared=prepared,
            execution_plan=execution_plan,
            policy_result=policy_result,
            policy_outcome=policy_outcome,
            tool_evidence=tool_evidence,
            intent_match=intent_match,
            action_plan=action_plan,
            execution_flow=execution_flow,
            conversation_state=conversation_state,
            tool_execution_mode=ToolExecutionMode.OFFICIAL,
            emit_authority=True,
        )

    def project(
        self,
        *,
        event: Event,
        prepared: CognitiveState,
        execution_plan: ExecutionPlan,
        policy_result: PolicyResult,
        policy_outcome: Dict[str, Any] | None,
        tool_evidence: Dict[str, Any],
        intent_match: Any,
        action_plan: Any,
        execution_flow: Any,
        conversation_state: ConversationState | None = None,
    ) -> RuntimeExecutorResult:
        if policy_result.decision == PolicyDecision.ESCALATE:
            return self._execute_interruption(
                mode="legacy_runtime_validation",
                event=event,
                prepared=prepared,
                execution_plan=execution_plan,
                policy_result=policy_result,
                policy_outcome=policy_outcome,
                tool_evidence=tool_evidence,
                conversation_state=conversation_state,
                emit_authority=False,
            )
        return self._execute_kernel_path(
            mode="legacy_runtime_validation",
            event=event,
            prepared=prepared,
            execution_plan=execution_plan,
            policy_result=policy_result,
            policy_outcome=policy_outcome,
            tool_evidence=tool_evidence,
            intent_match=intent_match,
            action_plan=action_plan,
            execution_flow=execution_flow,
            conversation_state=conversation_state,
            tool_execution_mode=ToolExecutionMode.SHADOW,
            emit_authority=False,
        )

    def _execute_interruption(
        self,
        *,
        mode: str,
        event: Event,
        prepared: CognitiveState,
        execution_plan: ExecutionPlan,
        policy_result: PolicyResult,
        policy_outcome: Dict[str, Any] | None,
        tool_evidence: Dict[str, Any],
        conversation_state: ConversationState | None,
        emit_authority: bool,
    ) -> RuntimeExecutorResult:
        step_outcomes: list[Dict[str, Any]] = []
        if policy_outcome and plan_has_step(execution_plan, "policy"):
            step_outcomes.append(policy_outcome)

        interruption_state = prepared
        interruption_step = _interruption_step(execution_plan)
        if interruption_step:
            interruption_execution = self.handlers.resolve(interruption_step).execute(
                StepExecutionContext(
                    state=prepared,
                    event=event,
                    execution_plan=execution_plan,
                    step=step_from_plan(execution_plan, interruption_step),
                    services=self.services,
                    conversation_state=conversation_state,
                    domain_context=self.domain_context,
                    policy_result=policy_result,
                    tool_evidence=tool_evidence,
                )
            )
            interruption_state = interruption_execution.state or prepared
            step_outcomes.append(interruption_execution.outcome)

        authorized = record_execution_authority(
            interruption_state,
            execution_plan=execution_plan,
            selected_program=None,
            executor="policy_manager",
            policy_result=policy_result,
            emit=self.emit if emit_authority else None,
        )
        final_state = self._finalize_state(
            authorized,
            policy_result,
            tool_evidence,
            event,
            execution_plan,
            step_outcomes,
            conversation_state,
        )
        return RuntimeExecutorResult(
            mode=mode,
            outcomes=list(final_state.facts.get("execution_step_outcomes", [])),
            final_state=final_state,
            execution_plan=execution_plan.to_dict(),
            policy_result=policy_result.to_dict(),
            tool_evidence=tool_evidence,
            selected_program=None,
            response=final_state.response,
            interrupted=True,
        )

    def _execute_kernel_path(
        self,
        *,
        mode: str,
        event: Event,
        prepared: CognitiveState,
        execution_plan: ExecutionPlan,
        policy_result: PolicyResult,
        policy_outcome: Dict[str, Any] | None,
        tool_evidence: Dict[str, Any],
        intent_match: Any,
        action_plan: Any,
        execution_flow: Any,
        conversation_state: ConversationState | None,
        tool_execution_mode: str,
        emit_authority: bool,
    ) -> RuntimeExecutorResult:
        graph = self.services.compiler.compile(event, prepared)
        authorized = record_execution_authority(
            prepared,
            execution_plan=execution_plan,
            selected_program=graph.name,
            executor="kernel",
            policy_result=policy_result,
            emit=self.emit if emit_authority else None,
        )
        step_outcomes: list[Dict[str, Any]] = []
        if policy_outcome and plan_has_step(execution_plan, "policy"):
            step_outcomes.append(policy_outcome)

        if plan_has_step(execution_plan, "tool_lookup"):
            tool_projection = RuntimeExecutor(
                handlers=self.handlers,
                services=self.services,
                domain_context=self.domain_context,
            ).execute_step_slice(
                event=event,
                state=prepared,
                execution_plan=execution_plan,
                step_names=["tool_lookup"],
                initial_policy_result=policy_result,
                initial_tool_evidence=tool_evidence,
                conversation_state=conversation_state,
                execution_mode=tool_execution_mode,
            )
            tool_evidence = tool_projection.tool_evidence or tool_evidence
            step_outcomes.extend(tool_projection.outcomes)

        kernel_execution = self.handlers.resolve("kernel").execute(
            StepExecutionContext(
                state=authorized,
                event=event,
                execution_plan=execution_plan,
                step=step_from_plan(execution_plan, "kernel"),
                services=self.services,
                conversation_state=conversation_state,
                domain_context=self.domain_context,
                policy_result=policy_result,
                tool_evidence=tool_evidence,
                runtime_context={
                    "graph": graph,
                    "intent_match": intent_match.to_dict(),
                    "action_plan": action_plan.to_dict(),
                    "execution_flow": execution_flow.to_dict(),
                    "execution_plan": execution_plan.to_dict(),
                    "execution_authority": authorized.facts.get("runtime_execution_authority", {}),
                    "policy_result": policy_result.to_dict(),
                    "tool_evidence": tool_evidence,
                },
            )
        )
        processed = kernel_execution.state or authorized
        if plan_has_step(execution_plan, "kernel"):
            step_outcomes.append(kernel_execution.outcome)

        final_state = self._finalize_state(
            processed,
            policy_result,
            tool_evidence,
            event,
            execution_plan,
            step_outcomes,
            conversation_state,
        )
        return RuntimeExecutorResult(
            mode=mode,
            outcomes=list(final_state.facts.get("execution_step_outcomes", [])),
            final_state=final_state,
            execution_plan=execution_plan.to_dict(),
            policy_result=policy_result.to_dict(),
            tool_evidence=tool_evidence,
            selected_program=graph.name,
            response=final_state.response,
        )

    def _finalize_state(
        self,
        state: CognitiveState,
        policy_result: PolicyResult,
        tool_evidence: Dict[str, Any],
        event: Event,
        execution_plan: ExecutionPlan,
        step_outcomes: list[Dict[str, Any]],
        conversation_state: ConversationState | None,
    ) -> CognitiveState:
        step_outcomes = list(step_outcomes)

        memory_result = self.handlers.resolve("memory").execute(
            StepExecutionContext(
                state=state,
                event=event,
                execution_plan=execution_plan,
                step=step_from_plan(execution_plan, "memory"),
                services=self.services,
                conversation_state=conversation_state,
                domain_context=self.domain_context,
                policy_result=policy_result,
                tool_evidence=tool_evidence,
            )
        )
        if plan_has_step(execution_plan, "memory"):
            step_outcomes.append(memory_result.outcome)

        context_result = self.handlers.resolve("context").execute(
            StepExecutionContext(
                state=memory_result.state or state,
                event=event,
                execution_plan=execution_plan,
                step=step_from_plan(execution_plan, "context"),
                services=self.services,
                conversation_state=conversation_state,
                domain_context=self.domain_context,
                policy_result=policy_result,
                tool_evidence=tool_evidence,
                runtime_context={"relevant_memory": memory_result.data.get("relevant_memory", [])},
            )
        )
        if plan_has_step(execution_plan, "context"):
            step_outcomes.append(context_result.outcome)

        output_result = self.handlers.resolve("output").execute(
            StepExecutionContext(
                state=context_result.state or memory_result.state or state,
                event=event,
                execution_plan=execution_plan,
                step=step_from_plan(execution_plan, "output"),
                services=self.services,
                conversation_state=conversation_state,
                domain_context=self.domain_context,
                policy_result=policy_result,
                tool_evidence=tool_evidence,
            )
        )
        if plan_has_step(execution_plan, "output"):
            step_outcomes.append(output_result.outcome)

        final_state = output_result.state or context_result.state or memory_result.state or state
        facts = dict(final_state.facts)
        facts["execution_step_outcomes"] = step_outcomes
        with_outcomes = final_state.evolve("EXECUTION_STEP_OUTCOMES", facts=facts)
        return self.conversation_manager.after_process(with_outcomes)


def _interruption_step(execution_plan: ExecutionPlan) -> str | None:
    names = execution_plan.step_names()
    if "escalation" in names:
        return "escalation"
    if "handoff" in names:
        return "handoff"
    return None
