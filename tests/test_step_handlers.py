import pytest

from aca_kernel.compiler.compiler import GraphCompiler
from aca_kernel.core.events import Event
from aca_kernel.core.kernel import ACAKernel
from aca_kernel.core.state import CognitiveState
from aca_kernel.plugins.rules.default_registry import build_default_registry
from aca_os.context_manager import ContextManager
from aca_os.memory_engine import MemoryEngine
from aca_os.mission_manager import MissionManager
from aca_os.policy_manager import PolicyDecision, PolicyManager, PolicyResult
from aca_os.step_handlers import (
    StepExecutionContext,
    StepHandlerRegistry,
    StepRuntimeServices,
    ToolLookupStepHandler,
    build_default_step_handler_registry,
    step_from_plan,
)
from aca_os.tool_engine import ToolEngine
from zero_cost.execution_plan import ExecutionPlan


def _services(tool_engine: ToolEngine | None = None) -> StepRuntimeServices:
    return StepRuntimeServices(
        policy_manager=PolicyManager(),
        tool_engine=tool_engine or ToolEngine(),
        compiler=GraphCompiler(),
        kernel=ACAKernel(build_default_registry()),
        mission_manager=MissionManager(),
        memory_engine=MemoryEngine(),
        context_manager=ContextManager(),
    )


def _plan(flow: str = "knowledge_lookup") -> ExecutionPlan:
    if flow == "knowledge_lookup":
        return ExecutionPlan.from_flow(
            {
                "flow": "knowledge_lookup",
                "source_action": "knowledge_lookup",
                "steps": ["policy", "tool_lookup", "kernel", "memory", "context", "output"],
                "payload": {"tool_key": "cleas"},
            }
        )
    return ExecutionPlan.from_flow(
        {
            "flow": "human_handoff",
            "source_action": "human_handoff",
            "steps": ["policy", "handoff", "memory", "context", "output"],
            "payload": {"reason": "explicit_human_request"},
        }
    )


def test_step_handler_registry_resolves_registered_handlers():
    registry = build_default_step_handler_registry()

    assert registry.can_handle("policy")
    assert registry.can_handle("tool_lookup")
    assert registry.resolve("kernel").step_name == "kernel"


def test_step_handler_registry_rejects_missing_handlers():
    registry = StepHandlerRegistry()

    with pytest.raises(KeyError):
        registry.resolve("missing_step")


def test_policy_handler_returns_uniform_contract():
    registry = build_default_step_handler_registry()
    plan = _plan("knowledge_lookup")

    result = registry.resolve("policy").execute(
        StepExecutionContext(
            state=CognitiveState(facts={"zero_cost_execution_plan": plan.to_dict()}),
            event=Event(type="user_message", payload="texto sin concepto"),
            execution_plan=plan,
            step=step_from_plan(plan, "policy"),
            services=_services(),
            domain_context={"concepts": {"cleas": {}}},
        )
    )

    assert result.status == "success"
    assert result.continue_execution is True
    assert result.policy_result is not None
    assert result.policy_result.decision == PolicyDecision.USE_TOOL
    assert result.outcome["step"] == "policy"
    assert result.outcome["executor"] == "policy_manager"


def test_policy_handler_reports_interruption_continuity():
    registry = build_default_step_handler_registry()
    plan = _plan("human_handoff")

    result = registry.resolve("policy").execute(
        StepExecutionContext(
            state=CognitiveState(facts={"zero_cost_execution_plan": plan.to_dict()}),
            event=Event(type="user_message", payload="texto sin pedido humano"),
            execution_plan=plan,
            step=step_from_plan(plan, "policy"),
            services=_services(),
            domain_context={},
        )
    )

    assert result.status == "interrupted"
    assert result.continue_execution is False
    assert result.interruption["reason"] == "user_requested_human"
    assert result.outcome["status"] == "interrupted"


def test_tool_lookup_handler_reports_controlled_error():
    plan = _plan("knowledge_lookup")
    result = ToolLookupStepHandler().execute(
        StepExecutionContext(
            state=CognitiveState(),
            event=Event(type="user_message", payload="Que es CLEAS?"),
            execution_plan=plan,
            step=step_from_plan(plan, "tool_lookup"),
            services=_services(ToolEngine()),
            policy_result=PolicyResult(
                decision=PolicyDecision.USE_TOOL,
                reason="execution_plan_tool_lookup_authorized",
                tool_key="cleas",
            ),
        )
    )

    assert result.status == "error"
    assert result.continue_execution is True
    assert result.error == "Tool not registered: knowledge_base"
    assert result.produced_evidence == {"tool_error": "Tool not registered: knowledge_base"}
    assert result.outcome["error"] == "Tool not registered: knowledge_base"


def test_output_handler_preserves_response_contract():
    registry = build_default_step_handler_registry()
    plan = _plan("knowledge_lookup")
    state = CognitiveState(response="respuesta final")

    result = registry.resolve("output").execute(
        StepExecutionContext(
            state=state,
            event=Event(type="user_message", payload="x"),
            execution_plan=plan,
            step=step_from_plan(plan, "output"),
            services=_services(),
        )
    )

    assert result.status == "success"
    assert result.state == state
    assert result.outcome["result"]["response"] == "respuesta final"
    assert result.state_changes["response_present"] is True
