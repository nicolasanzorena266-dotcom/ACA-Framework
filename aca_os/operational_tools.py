from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from aca_os.tool_engine import (
    ToolExecutionContract,
    ToolExecutionContext,
    ToolIdempotency,
    ToolRequest,
    ToolResult,
)


class JsonlHandoffPackageStore:
    """Append-only store that represents the first reversible operational system."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: Mapping[str, Any]) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        stored = deepcopy(dict(record))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(stored, ensure_ascii=False, sort_keys=True) + "\n")
        return stored

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        records: list[dict[str, Any]] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                records.append(parsed)
        return records

    def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        if not key:
            return None
        for record in self.records():
            receipt = _mapping(record.get("external_receipt"))
            if receipt.get("idempotency_key") == key:
                return record
        return None


class HandoffPackageAdapter:
    """Prepare and persist a real handoff package with a reversible local receipt."""

    name = "handoff_package"
    execution_contract = ToolExecutionContract(
        deterministic=False,
        has_side_effects=True,
        supports_dry_run=True,
        supports_replay=True,
        supports_shadow=False,
        idempotency=ToolIdempotency.IDEMPOTENT,
        guarantee="Persists an internal handoff package and returns a stable reversible receipt.",
    )

    def __init__(self, store_path: str | Path | None = None) -> None:
        self.store = JsonlHandoffPackageStore(
            store_path or Path(".aca") / "operational" / "handoff_packages.jsonl"
        )

    def execute(self, request: ToolRequest, context: ToolExecutionContext | None = None) -> ToolResult:
        context = context or ToolExecutionContext()
        payload = dict(request.payload or {})
        failure_mode = str(payload.get("failure_mode") or "")
        if failure_mode:
            return self._failed_result(request, context, failure_mode=failure_mode)

        evidence = self._build_evidence(request, context, mode="official")
        receipt = _mapping(evidence.get("external_receipt"))
        idempotency_key = str(receipt.get("idempotency_key") or "")
        existing = self.store.find_by_idempotency_key(idempotency_key)
        if existing:
            existing_evidence = _mapping(existing.get("evidence"))
            existing_receipt = _mapping(existing.get("external_receipt"))
            replayed = deepcopy(existing_evidence)
            replayed["external_receipt"] = {
                **existing_receipt,
                "status": "duplicate_replayed",
                "external_status": "duplicate_replayed",
                "duplicate": True,
            }
            replayed["tool_response"] = {
                "status": "duplicate_replayed",
                "package_id": existing_receipt.get("receipt_id"),
                "write_performed": False,
            }
            return ToolResult(tool_name=self.name, success=True, evidence=replayed)

        package_record = {
            "contract": "operational_handoff_package_record.v1",
            "package_id": receipt.get("receipt_id"),
            "conversation_id": receipt.get("conversation_id"),
            "idempotency_key": idempotency_key,
            "operation": receipt.get("operation"),
            "status": "active",
            "reversible": True,
            "compensation_action": "void_handoff_package",
            "request": deepcopy(_mapping(evidence.get("tool_request"))),
            "response": deepcopy(_mapping(evidence.get("tool_response"))),
            "external_receipt": deepcopy(receipt),
            "evidence": deepcopy(evidence),
        }
        self.store.append(package_record)
        return ToolResult(tool_name=self.name, success=True, evidence=evidence)

    def dry_run(self, request: ToolRequest, context: ToolExecutionContext | None = None) -> ToolResult:
        context = context or ToolExecutionContext()
        evidence = self._build_evidence(request, context, mode="dry_run")
        return ToolResult(tool_name=self.name, success=True, evidence=evidence)

    def replay(self, request: ToolRequest, context: ToolExecutionContext | None = None) -> ToolResult:
        context = context or ToolExecutionContext()
        evidence = dict(context.replay_evidence or context.existing_evidence)
        if evidence:
            return ToolResult(tool_name=self.name, success=True, evidence=evidence)
        payload = dict(request.payload or {})
        idempotency_key = str(payload.get("idempotency_key") or "")
        existing = self.store.find_by_idempotency_key(idempotency_key)
        if existing:
            return ToolResult(tool_name=self.name, success=True, evidence=dict(_mapping(existing.get("evidence"))))
        return ToolResult(tool_name=self.name, success=False, error="Replay evidence not available.")

    def _build_evidence(
        self,
        request: ToolRequest,
        context: ToolExecutionContext,
        *,
        mode: str,
    ) -> dict[str, Any]:
        payload = dict(request.payload or {})
        selected_work = _mapping(payload.get("selected_work"))
        governance = _mapping(payload.get("governance_assessment"))
        ledger = _mapping(payload.get("ledger_record"))
        case_state = _mapping(payload.get("case_state_projection"))
        candidate_work = list(payload.get("candidate_work") or [])
        conversation_id = str(payload.get("conversation_id") or ledger.get("conversation_id") or "")
        operation = str(selected_work.get("operation") or "prepare_handoff")
        idempotency_key = str(payload.get("idempotency_key") or _mapping(ledger.get("idempotency")).get("key") or "")
        if not idempotency_key:
            idempotency_key = _stable_id("handoff-idempotency", conversation_id, operation, json.dumps(selected_work, sort_keys=True, default=str))
        receipt_id = _stable_id(
            "handoff-package",
            conversation_id,
            operation,
            idempotency_key,
            json.dumps(selected_work, sort_keys=True, default=str),
        )
        package = {
            "summary": _summary(selected_work=selected_work, case_state=case_state, governance=governance),
            "selected_work": deepcopy(selected_work),
            "candidate_work": deepcopy(candidate_work),
            "case_stage": case_state.get("stage") or case_state.get("case_stage") or "unknown",
            "responsible_owner": _responsible_owner(governance, case_state),
            "required_evidence": list(_mapping(governance.get("evidence")).get("required") or []),
            "available_evidence": deepcopy(_available_evidence(payload, governance, ledger)),
            "missing_preconditions": deepcopy(list(governance.get("missing_preconditions") or [])),
            "next_operational_step": _next_step(selected_work, governance),
        }
        projected_request = {
            "tool": self.name,
            "intent": request.intent,
            "operation": operation,
            "conversation_id": conversation_id,
            "idempotency_key": idempotency_key,
            "mode": mode,
            "dry_run": mode == "dry_run",
            "package": deepcopy(package),
        }
        projected_response = {
            "status": "prepared" if mode == "dry_run" else "created",
            "operation": operation,
            "handoff_package_ready": True,
            "package_id": receipt_id,
            "external_write": mode != "dry_run",
            "side_effects": mode != "dry_run",
            "write_performed": mode != "dry_run",
        }
        receipt = {
            "contract": "operational_handoff_package_receipt.v1",
            "receipt_id": receipt_id,
            "status": "dry_run_completed" if mode == "dry_run" else "created",
            "external_status": "not_executed" if mode == "dry_run" else "stored",
            "operation": operation,
            "tool": self.name,
            "conversation_id": conversation_id,
            "idempotency_key": idempotency_key,
            "external_write": mode != "dry_run",
            "side_effects": mode != "dry_run",
            "replayable": True,
            "reversible": True,
            "compensation_action": "void_handoff_package",
            "storage": {
                "type": "jsonl",
                "path": str(self.store.path),
            },
        }
        evidence = {
            "contract": "operational_handoff_package.v1",
            "tool": self.name,
            "mode": mode,
            "source": "tool_contract",
            "mutates_state": False,
            "changes_response": False,
            "selected_work": deepcopy(selected_work),
            "governance_decision": deepcopy(_mapping(ledger.get("governance_decision")) or governance),
            "tool_request": projected_request,
            "tool_response": projected_response,
            "projected_request": projected_request,
            "projected_response": projected_response,
            "projected_receipt": receipt,
            "external_receipt": receipt,
            "handoff_package": package,
            "ledger": deepcopy(ledger),
        }
        return evidence

    def _failed_result(
        self,
        request: ToolRequest,
        context: ToolExecutionContext,
        *,
        failure_mode: str,
    ) -> ToolResult:
        evidence = self._build_evidence(request, context, mode="official")
        receipt = dict(_mapping(evidence.get("external_receipt")))
        if failure_mode == "invalid_receipt":
            receipt["receipt_id"] = ""
            receipt["status"] = "invalid_receipt"
            receipt["external_status"] = "invalid_receipt"
            error = "Invalid receipt returned by internal handoff package store."
        elif failure_mode == "timeout":
            receipt["status"] = "timeout"
            receipt["external_status"] = "timeout"
            error = "Internal handoff package store timed out."
        elif failure_mode == "tool_down":
            receipt["status"] = "tool_down"
            receipt["external_status"] = "tool_down"
            error = "Internal handoff package store unavailable."
        else:
            receipt["status"] = "tool_error"
            receipt["external_status"] = "tool_error"
            error = f"Unsupported simulated production failure: {failure_mode}"
        receipt["external_write"] = False
        receipt["side_effects"] = False
        evidence["external_receipt"] = receipt
        evidence["projected_receipt"] = receipt
        evidence["tool_response"] = {
            "status": receipt["status"],
            "operation": receipt.get("operation"),
            "write_performed": False,
            "error": error,
        }
        evidence["projected_response"] = evidence["tool_response"]
        return ToolResult(tool_name=self.name, success=False, evidence=evidence, error=error)


class HandoffPackageDryRunAdapter(HandoffPackageAdapter):
    """Backward-compatible name for the dry-run benchmark adapter."""


def _summary(
    *,
    selected_work: Mapping[str, Any],
    case_state: Mapping[str, Any],
    governance: Mapping[str, Any],
) -> str:
    operation = str(selected_work.get("operation") or "prepare_handoff")
    stage = str(case_state.get("stage") or case_state.get("case_stage") or "case_state_unknown")
    allowed = "allowed" if governance.get("execution_allowed") else "blocked"
    return f"{operation} projected for {stage}; governance={allowed}."


def _responsible_owner(governance: Mapping[str, Any], case_state: Mapping[str, Any]) -> str:
    owner = str(case_state.get("responsible_owner") or case_state.get("responsible") or "")
    if owner:
        return owner
    risk = _mapping(governance.get("risk"))
    if int(risk.get("level") or 0) >= 3:
        return "specialized_operations"
    return "customer_service_representative"


def _available_evidence(
    payload: Mapping[str, Any],
    governance: Mapping[str, Any],
    ledger: Mapping[str, Any],
) -> dict[str, Any]:
    evidence = _mapping(ledger.get("evidence")) or _mapping(governance.get("evidence"))
    if evidence:
        return evidence
    mapped_work = _mapping(payload.get("mapped_work"))
    return _mapping(mapped_work.get("evidence"))


def _next_step(selected_work: Mapping[str, Any], governance: Mapping[str, Any]) -> str:
    if governance.get("execution_blocked"):
        return "resolve_governance_preconditions"
    operation = str(selected_work.get("operation") or "")
    if operation == "prepare_handoff":
        return "handoff_package_ready_for_review"
    return "operational_package_ready"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _stable_id(*parts: str) -> str:
    payload = "|".join(parts)
    return sha256(payload.encode("utf-8")).hexdigest()[:24]
