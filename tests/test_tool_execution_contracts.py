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
from aca_os.runtime import ACAOSRuntime
from aca_os.step_handlers import StepExecutionContext, StepRuntimeServices, ToolLookupStepHandler, step_from_plan
from aca_os.tool_engine import (
    StaticKnowledgeAdapter,
    ToolEngine,
    ToolExecutionContext,
    ToolExecutionContract,
    ToolExecutionMode,
    ToolIdempotency,
    ToolRequest,
    ToolResult,
)
from zero_cost.execution_plan import ExecutionPlan
from sdk.factory import build_galicia_runtime
from domains.galicia.domain_pack import load_galicia_domain


class _SideEffectAdapter:
    name = "writer"
    execution_contract = ToolExecutionContract(
        deterministic=False,
        has_side_effects=True,
        supports_dry_run=False,
        supports_replay=False,
        supports_shadow=False,
        idempotency=ToolIdempotency.NON_IDEMPOTENT,
        guarantee="Writes to an external system.",
    )

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, request: ToolRequest, context: ToolExecutionContext | None = None) -> ToolResult:
        self.calls += 1
        return ToolResult(tool_name=self.name, success=True, evidence={"written": self.calls})


class _DryRunAdapter(_SideEffectAdapter):
    name = "dry_writer"
    execution_contract = ToolExecutionContract(
        deterministic=False,
        has_side_effects=True,
        supports_dry_run=True,
        supports_replay=False,
        supports_shadow=False,
        idempotency=ToolIdempotency.NON_IDEMPOTENT,
        guarantee="Dry-run returns a simulated write.",
    )

    def dry_run(self, request: ToolRequest, context: ToolExecutionContext | None = None) -> ToolResult:
        return ToolResult(tool_name=self.name, success=True, evidence={"dry_run": True})


class _ReplayAdapter(_SideEffectAdapter):
    name = "replay_writer"
    execution_contract = ToolExecutionContract(
        deterministic=False,
        has_side_effects=True,
        supports_dry_run=False,
        supports_replay=True,
        supports_shadow=False,
        idempotency=ToolIdempotency.NON_IDEMPOTENT,
        guarantee="Replay uses captured evidence.",
    )


class _SideEffectKnowledgeAdapter(_SideEffectAdapter):
    name = "knowledge_base"

    def execute(self, request: ToolRequest, context: ToolExecutionContext | None = None) -> ToolResult:
        self.calls += 1
        key = str(request.payload.get("key", "cleas"))
        return ToolResult(
            tool_name=self.name,
            success=True,
            evidence={
                key: {
                    "name": "CLEAS",
                    "simple_explanation": "captured from official execution",
                }
            },
        )


class _InvalidShadowAdapter(_SideEffectAdapter):
    name = "invalid_shadow_writer"
    execution_contract = ToolExecutionContract(
        deterministic=False,
        has_side_effects=True,
        supports_dry_run=False,
        supports_replay=False,
        supports_shadow=True,
        idempotency=ToolIdempotency.NON_IDEMPOTENT,
    )


class _LegacyAdapter:
    name = "legacy"

    def execute(self, request: ToolRequest) -> ToolResult:
        return ToolResult(tool_name=self.name, success=True)


def _request(tool_name: str) -> ToolRequest:
    return ToolRequest(tool_name=tool_name, intent="test", payload={"key": "cleas"})


def _services(tool_engine: ToolEngine) -> StepRuntimeServices:
    return StepRuntimeServices(
        policy_manager=PolicyManager(),
        tool_engine=tool_engine,
        compiler=GraphCompiler(),
        kernel=ACAKernel(build_default_registry()),
        mission_manager=MissionManager(),
        memory_engine=MemoryEngine(),
        context_manager=ContextManager(),
    )


def _knowledge_plan() -> ExecutionPlan:
    return ExecutionPlan.from_flow(
        {
            "flow": "knowledge_lookup",
            "source_action": "knowledge_lookup",
            "steps": ["policy", "tool_lookup", "kernel", "memory", "context", "output"],
            "payload": {"tool_key": "cleas"},
        }
    )


def _runtime_with_tool(adapter) -> ACAOSRuntime:
    domain = load_galicia_domain()
    tool_engine = ToolEngine()
    tool_engine.register(adapter)
    return ACAOSRuntime(
        kernel=ACAKernel(build_default_registry()),
        compiler=GraphCompiler(),
        mission_manager=MissionManager(),
        tool_engine=tool_engine,
        domain_context=domain.context(),
    )


def test_static_knowledge_adapter_declares_safe_shadow_contract():
    engine = ToolEngine()
    engine.register(StaticKnowledgeAdapter({"cleas": {"summary": "Convenio entre aseguradoras."}}))

    result = engine.execute(
        _request("knowledge_base"),
        context=ToolExecutionContext(mode=ToolExecutionMode.SHADOW, runtime_engine="runtime_executor_shadow"),
    )

    assert result.success is True
    assert result.evidence["cleas"]["summary"] == "Convenio entre aseguradoras."
    assert result.execution["action"] == "execute"
    assert result.execution["executed"] is True
    assert result.execution["mode"] == "shadow"
    assert result.execution["execution_contract"]["deterministic"] is True
    assert result.execution["execution_contract"]["has_side_effects"] is False


def test_side_effect_tool_executes_officially_but_not_in_shadow_with_existing_evidence():
    adapter = _SideEffectAdapter()
    engine = ToolEngine()
    engine.register(adapter)

    official = engine.execute(_request("writer"), context=ToolExecutionContext(mode=ToolExecutionMode.OFFICIAL))
    shadow = engine.execute(
        _request("writer"),
        context=ToolExecutionContext(
            mode=ToolExecutionMode.SHADOW,
            existing_evidence={"written": 1},
            runtime_engine="runtime_executor_shadow",
        ),
    )

    assert official.success is True
    assert official.execution["executed"] is True
    assert shadow.success is True
    assert shadow.evidence == {"written": 1}
    assert shadow.execution["action"] == "reuse_existing_evidence"
    assert shadow.execution["executed"] is False
    assert adapter.calls == 1


def test_shadow_uses_dry_run_when_contract_allows_it():
    adapter = _DryRunAdapter()
    engine = ToolEngine()
    engine.register(adapter)

    result = engine.execute(_request("dry_writer"), context=ToolExecutionContext(mode=ToolExecutionMode.SHADOW))

    assert result.success is True
    assert result.evidence == {"dry_run": True}
    assert result.execution["action"] == "dry_run"
    assert result.execution["executed"] is False
    assert adapter.calls == 0


def test_replay_mode_uses_captured_evidence_without_execution():
    adapter = _ReplayAdapter()
    engine = ToolEngine()
    engine.register(adapter)

    result = engine.execute(
        _request("replay_writer"),
        context=ToolExecutionContext(mode=ToolExecutionMode.REPLAY, replay_evidence={"replayed": True}),
    )

    assert result.success is True
    assert result.evidence == {"replayed": True}
    assert result.execution["action"] == "replay"
    assert result.execution["executed"] is False
    assert adapter.calls == 0


def test_unsafe_shadow_execution_is_rejected_without_replay_dry_run_or_existing_evidence():
    adapter = _SideEffectAdapter()
    engine = ToolEngine()
    engine.register(adapter)

    result = engine.execute(_request("writer"), context=ToolExecutionContext(mode=ToolExecutionMode.SHADOW))

    assert result.success is False
    assert result.error == "tool_cannot_run_safely_in_shadow"
    assert result.execution["action"] == "reject"
    assert result.execution["executed"] is False
    assert adapter.calls == 0


def test_invalid_contracts_are_rejected_at_registration():
    engine = ToolEngine()

    with pytest.raises(ValueError):
        engine.register(_InvalidShadowAdapter())

    with pytest.raises(ValueError):
        engine.register(_LegacyAdapter())


def test_tool_lookup_handler_reuses_existing_evidence_in_shadow_for_unsafe_tool():
    adapter = _SideEffectAdapter()
    adapter.name = "knowledge_base"
    engine = ToolEngine()
    engine.register(adapter)
    plan = _knowledge_plan()

    result = ToolLookupStepHandler().execute(
        StepExecutionContext(
            state=CognitiveState(facts={"zero_cost_execution_plan": plan.to_dict()}),
            event=Event(type="user_message", payload="Que es CLEAS?"),
            execution_plan=plan,
            step=step_from_plan(plan, "tool_lookup"),
            services=_services(engine),
            policy_result=PolicyResult(
                decision=PolicyDecision.USE_TOOL,
                reason="execution_plan_tool_lookup_authorized",
                tool_key="cleas",
            ),
            tool_evidence={"cleas": {"summary": "captured"}},
            runtime_config={
                "tool_execution_mode": ToolExecutionMode.SHADOW,
                "runtime_engine": "runtime_executor_shadow",
            },
        )
    )

    assert result.status == "success"
    assert result.produced_evidence == {"cleas": {"summary": "captured"}}
    assert result.outcome["result"]["tool_execution"]["action"] == "reuse_existing_evidence"
    assert result.outcome["result"]["tool_execution"]["executed"] is False
    assert adapter.calls == 0


def test_runtime_introspection_exposes_tool_execution_contract():
    runtime = build_galicia_runtime()

    runtime.process(Event(type="user_message", payload="Que es CLEAS?"))
    snapshot = runtime.inspect_runtime().to_dict()
    execution = snapshot["last_state"]["tool_executions"][0]

    assert execution["tool_name"] == "knowledge_base"
    assert execution["mode"] == "official"
    assert execution["action"] == "execute"
    assert execution["supports_shadow"] is True
    assert execution["has_side_effects"] is False
    assert execution["idempotency"] == "idempotent"


def test_runtime_delegates_tool_lookup_ownership_to_runtime_executor_without_duplication():
    adapter = _SideEffectKnowledgeAdapter()
    runtime = _runtime_with_tool(adapter)

    state = runtime.process(Event(type="user_message", payload="Que es CLEAS?"))
    official_tool = next(outcome for outcome in state.facts["execution_step_outcomes"] if outcome["step"] == "tool_lookup")
    shadow_tool = next(
        outcome
        for outcome in state.facts["runtime_executor_shadow"]["shadow"]["outcomes"]
        if outcome["step"] == "tool_lookup"
    )

    assert adapter.calls == 1
    assert state.facts["runtime_execution_engine"]["official_engine"] == "runtime_executor"
    assert state.facts["runtime_execution_engine"]["selection_reason"] == "migrated_flow_slice_3"
    assert state.response.startswith("CLEAS: captured from official execution")
    assert official_tool["result"]["tool_execution"]["owner"] == "runtime_executor"
    assert official_tool["result"]["tool_execution"]["mode"] == "official"
    assert official_tool["result"]["tool_execution"]["action"] == "execute"
    assert official_tool["result"]["tool_execution"]["executed"] is True
    assert shadow_tool["result"]["tool_execution"]["action"] == "reuse_existing_evidence"
    assert shadow_tool["result"]["tool_execution"]["executed"] is False
    assert state.facts["runtime_executor_shadow"]["equivalent"] is True
