from dataclasses import dataclass, field
from typing import Any, Dict, Protocol


class ToolExecutionMode:
    OFFICIAL = "official"
    SHADOW = "shadow"
    DRY_RUN = "dry_run"
    REPLAY = "replay"
    SIMULATION = "simulation"


class ToolExecutionAction:
    EXECUTE = "execute"
    DRY_RUN = "dry_run"
    REPLAY = "replay"
    REUSE_EXISTING_EVIDENCE = "reuse_existing_evidence"
    REJECT = "reject"


class ToolIdempotency:
    IDEMPOTENT = "idempotent"
    REQUIRES_IDEMPOTENCY_KEY = "requires_idempotency_key"
    NON_IDEMPOTENT = "non_idempotent"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ToolExecutionContract:
    deterministic: bool
    has_side_effects: bool
    supports_dry_run: bool
    supports_replay: bool
    supports_shadow: bool
    idempotency: str
    guarantee: str = ""

    def validate(self) -> None:
        valid_idempotency = {
            ToolIdempotency.IDEMPOTENT,
            ToolIdempotency.REQUIRES_IDEMPOTENCY_KEY,
            ToolIdempotency.NON_IDEMPOTENT,
            ToolIdempotency.UNKNOWN,
        }
        if self.idempotency not in valid_idempotency:
            raise ValueError(f"Invalid tool idempotency guarantee: {self.idempotency}")
        if self.has_side_effects and self.supports_shadow and self.idempotency == ToolIdempotency.NON_IDEMPOTENT:
            raise ValueError("Non-idempotent side-effect tools cannot opt into direct shadow execution.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deterministic": self.deterministic,
            "has_side_effects": self.has_side_effects,
            "supports_dry_run": self.supports_dry_run,
            "supports_replay": self.supports_replay,
            "supports_shadow": self.supports_shadow,
            "idempotency": self.idempotency,
            "guarantee": self.guarantee,
        }


@dataclass(frozen=True)
class ToolExecutionContext:
    mode: str = ToolExecutionMode.OFFICIAL
    origin: str = "runtime"
    execution_plan: Dict[str, Any] = field(default_factory=dict)
    runtime_engine: str = "legacy_runtime"
    permissions: Dict[str, Any] = field(default_factory=dict)
    simulation: Dict[str, Any] = field(default_factory=dict)
    existing_evidence: Dict[str, Any] = field(default_factory=dict)
    replay_evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "origin": self.origin,
            "execution_plan": dict(self.execution_plan),
            "runtime_engine": self.runtime_engine,
            "permissions": dict(self.permissions),
            "simulation": dict(self.simulation),
            "existing_evidence_keys": sorted(self.existing_evidence.keys()),
            "replay_evidence_keys": sorted(self.replay_evidence.keys()),
        }


@dataclass(frozen=True)
class ToolRequest:
    tool_name: str
    intent: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    tool_name: str
    success: bool
    evidence: Dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    execution: Dict[str, Any] = field(default_factory=dict)


class ToolAdapter(Protocol):
    name: str
    execution_contract: ToolExecutionContract

    def execute(self, request: ToolRequest, context: ToolExecutionContext | None = None) -> ToolResult:
        raise NotImplementedError


class ToolEngine:
    def __init__(self) -> None:
        self._adapters: Dict[str, ToolAdapter] = {}
        self._contracts: Dict[str, ToolExecutionContract] = {}

    def register(self, adapter: ToolAdapter) -> None:
        contract = getattr(adapter, "execution_contract", None)
        if contract is None:
            raise ValueError(f"Tool adapter must declare execution_contract: {adapter.name}")
        contract.validate()
        self._adapters[adapter.name] = adapter
        self._contracts[adapter.name] = contract

    def can_execute(self, tool_name: str) -> bool:
        return tool_name in self._adapters

    def contract_for(self, tool_name: str) -> ToolExecutionContract | None:
        return self._contracts.get(tool_name)

    def execute(self, request: ToolRequest, context: ToolExecutionContext | None = None) -> ToolResult:
        context = context or ToolExecutionContext()
        if request.tool_name not in self._adapters:
            execution = _execution_record(
                tool_name=request.tool_name,
                context=context,
                contract=None,
                action=ToolExecutionAction.REJECT,
                executed=False,
                reason="tool_not_registered",
            )
            return ToolResult(
                tool_name=request.tool_name,
                success=False,
                error=f"Tool not registered: {request.tool_name}",
                execution=execution,
            )

        adapter = self._adapters[request.tool_name]
        contract = self._contracts[request.tool_name]
        decision = _decide_execution(context, contract)

        if decision["action"] == ToolExecutionAction.REJECT:
            return ToolResult(
                tool_name=request.tool_name,
                success=False,
                error=decision["reason"],
                execution=_execution_record(
                    tool_name=request.tool_name,
                    context=context,
                    contract=contract,
                    action=decision["action"],
                    executed=False,
                    reason=decision["reason"],
                ),
            )

        if decision["action"] == ToolExecutionAction.REUSE_EXISTING_EVIDENCE:
            return ToolResult(
                tool_name=request.tool_name,
                success=True,
                evidence=dict(context.existing_evidence),
                execution=_execution_record(
                    tool_name=request.tool_name,
                    context=context,
                    contract=contract,
                    action=decision["action"],
                    executed=False,
                    reason=decision["reason"],
                ),
            )

        if decision["action"] == ToolExecutionAction.REPLAY:
            replay = getattr(adapter, "replay", None)
            if callable(replay):
                result = replay(request, context)
                return _with_execution(result, context, contract, decision, executed=False)
            evidence = dict(context.replay_evidence or context.existing_evidence)
            return ToolResult(
                tool_name=request.tool_name,
                success=bool(evidence),
                evidence=evidence,
                error=None if evidence else "Replay evidence not available.",
                execution=_execution_record(
                    tool_name=request.tool_name,
                    context=context,
                    contract=contract,
                    action=decision["action"],
                    executed=False,
                    reason=decision["reason"],
                ),
            )

        if decision["action"] == ToolExecutionAction.DRY_RUN:
            dry_run = getattr(adapter, "dry_run", None)
            result = dry_run(request, context) if callable(dry_run) else ToolResult(tool_name=request.tool_name, success=True)
            return _with_execution(result, context, contract, decision, executed=False)

        result = adapter.execute(request, context)
        return _with_execution(result, context, contract, decision, executed=True)


class StaticKnowledgeAdapter:
    name = "knowledge_base"
    execution_contract = ToolExecutionContract(
        deterministic=True,
        has_side_effects=False,
        supports_dry_run=True,
        supports_replay=True,
        supports_shadow=True,
        idempotency=ToolIdempotency.IDEMPOTENT,
        guarantee="Static in-memory lookup; no external writes or remote calls.",
    )

    def __init__(self, knowledge: Dict[str, Any] | None = None) -> None:
        self.knowledge = knowledge or {}

    def execute(self, request: ToolRequest, context: ToolExecutionContext | None = None) -> ToolResult:
        key = str(request.payload.get("key", ""))
        if key not in self.knowledge:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Knowledge key not found: {key}",
            )
        return ToolResult(
            tool_name=self.name,
            success=True,
            evidence={key: self.knowledge[key]},
        )

    def dry_run(self, request: ToolRequest, context: ToolExecutionContext | None = None) -> ToolResult:
        return self.execute(request, context)

    def replay(self, request: ToolRequest, context: ToolExecutionContext | None = None) -> ToolResult:
        context = context or ToolExecutionContext()
        evidence = dict(context.replay_evidence or context.existing_evidence)
        if evidence:
            return ToolResult(tool_name=self.name, success=True, evidence=evidence)
        return self.execute(request, context)


def _decide_execution(context: ToolExecutionContext, contract: ToolExecutionContract) -> Dict[str, str]:
    if context.mode == ToolExecutionMode.OFFICIAL:
        return {"action": ToolExecutionAction.EXECUTE, "reason": "official_execution"}

    if context.mode == ToolExecutionMode.DRY_RUN:
        if contract.supports_dry_run:
            return {"action": ToolExecutionAction.DRY_RUN, "reason": "dry_run_requested"}
        return {"action": ToolExecutionAction.REJECT, "reason": "tool_does_not_support_dry_run"}

    if context.mode == ToolExecutionMode.REPLAY:
        if contract.supports_replay:
            return {"action": ToolExecutionAction.REPLAY, "reason": "replay_requested"}
        return {"action": ToolExecutionAction.REJECT, "reason": "tool_does_not_support_replay"}

    if context.mode == ToolExecutionMode.SIMULATION:
        if contract.supports_dry_run:
            return {"action": ToolExecutionAction.DRY_RUN, "reason": "simulation_uses_dry_run"}
        if contract.supports_replay:
            return {"action": ToolExecutionAction.REPLAY, "reason": "simulation_uses_replay"}
        if context.existing_evidence:
            return {"action": ToolExecutionAction.REUSE_EXISTING_EVIDENCE, "reason": "simulation_reuses_existing_evidence"}
        return {"action": ToolExecutionAction.REJECT, "reason": "tool_cannot_run_in_simulation"}

    if context.mode == ToolExecutionMode.SHADOW:
        if context.existing_evidence:
            return {"action": ToolExecutionAction.REUSE_EXISTING_EVIDENCE, "reason": "shadow_reuses_existing_evidence"}
        if contract.supports_shadow and not contract.has_side_effects:
            return {"action": ToolExecutionAction.EXECUTE, "reason": "shadow_execution_allowed_by_contract"}
        if contract.supports_dry_run:
            return {"action": ToolExecutionAction.DRY_RUN, "reason": "shadow_uses_dry_run"}
        if contract.supports_replay:
            return {"action": ToolExecutionAction.REPLAY, "reason": "shadow_uses_replay"}
        return {"action": ToolExecutionAction.REJECT, "reason": "tool_cannot_run_safely_in_shadow"}

    return {"action": ToolExecutionAction.REJECT, "reason": f"unsupported_tool_execution_mode:{context.mode}"}


def _with_execution(
    result: ToolResult,
    context: ToolExecutionContext,
    contract: ToolExecutionContract,
    decision: Dict[str, str],
    *,
    executed: bool,
) -> ToolResult:
    return ToolResult(
        tool_name=result.tool_name,
        success=result.success,
        evidence=dict(result.evidence),
        error=result.error,
        execution=_execution_record(
            tool_name=result.tool_name,
            context=context,
            contract=contract,
            action=decision["action"],
            executed=executed,
            reason=decision["reason"],
        ),
    )


def _execution_record(
    *,
    tool_name: str,
    context: ToolExecutionContext,
    contract: ToolExecutionContract | None,
    action: str,
    executed: bool,
    reason: str,
) -> Dict[str, Any]:
    return {
        "contract": "tool_execution_record.v1",
        "tool_name": tool_name,
        "mode": context.mode,
        "origin": context.origin,
        "runtime_engine": context.runtime_engine,
        "owner": context.runtime_engine,
        "action": action,
        "executed": executed,
        "reason": reason,
        "execution_contract": contract.to_dict() if contract else {},
        "context": context.to_dict(),
    }
