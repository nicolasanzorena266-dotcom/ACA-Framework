from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class JsonlOperationalAuditLedgerStore:
    """Durable append-only store for operational audit ledger records."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def persist(self, record: Mapping[str, Any]) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        persisted = deepcopy(dict(record))
        persisted["persistent"] = True
        persisted.setdefault("audit_trail", [])
        persisted["audit_trail"] = list(persisted["audit_trail"]) + [
            {
                "event": "ledger_persisted",
                "source": "jsonl_operational_audit_ledger_store",
                "path": str(self.path),
            }
        ]
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(persisted, ensure_ascii=False, sort_keys=True) + "\n")
        return persisted

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

    def find_by_ledger_id(self, ledger_id: str) -> dict[str, Any] | None:
        for record in self.records():
            if record.get("ledger_id") == ledger_id:
                return record
        return None


def project_operational_audit_ledger(
    mapped_work: Mapping[str, Any],
    governance_assessment: Mapping[str, Any],
    *,
    tool_contracts: Mapping[str, Any] | None = None,
    execution_plan: Mapping[str, Any] | None = None,
    runtime_outcomes: Sequence[Mapping[str, Any]] = (),
    ledger_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project how a real operational execution would be audited.

    The ledger is shadow-only. It does not persist data, execute tools, authorize
    work or mutate Runtime state.
    """

    tool_contracts = dict(tool_contracts or {})
    execution_plan = _mapping(execution_plan)
    runtime_outcomes = list(runtime_outcomes or [])
    ledger_context = dict(ledger_context or {})
    selected_work = _mapping(governance_assessment.get("selected_work")) or _mapping(mapped_work.get("selected_work"))
    operation = str(selected_work.get("operation") or "no_operational_work_identified")
    tool = _mapping(governance_assessment.get("tool_availability"))
    idempotency = _mapping(governance_assessment.get("idempotency"))
    risk = _mapping(governance_assessment.get("risk"))
    confirmation = _confirmation_status(governance_assessment, ledger_context)
    approval = _approval_status(governance_assessment, ledger_context)
    conversation_id = _conversation_id(mapped_work, ledger_context)
    timestamp = _timestamp(runtime_outcomes, ledger_context)
    idempotency_record = _idempotency_record(
        operation=operation,
        conversation_id=conversation_id,
        tool=tool,
        idempotency=idempotency,
        ledger_context=ledger_context,
    )
    duplicate = _duplicate_detection(
        operation=operation,
        tool=tool,
        idempotency_record=idempotency_record,
        ledger_context=ledger_context,
    )
    projected_request = _projected_request(
        operation=operation,
        selected_work=selected_work,
        governance_assessment=governance_assessment,
        tool=tool,
        execution_plan=execution_plan,
    )
    external_receipt = _external_receipt(
        governance_assessment=governance_assessment,
        ledger_context=ledger_context,
    )
    execution_status = _execution_status(
        governance_assessment=governance_assessment,
        approval=approval,
        confirmation=confirmation,
        duplicate=duplicate,
        external_receipt=external_receipt,
        ledger_context=ledger_context,
    )
    compensation = _compensation_strategy(
        governance_assessment=governance_assessment,
        execution_status=execution_status,
    )
    evidence = _evidence_record(mapped_work, governance_assessment)
    preconditions = _preconditions(governance_assessment)
    audit_trail = _audit_trail(
        selected_work=selected_work,
        governance_assessment=governance_assessment,
        projected_request=projected_request,
        execution_status=execution_status,
        external_receipt=external_receipt,
        duplicate=duplicate,
    )
    ledger_id = _stable_id(
        "operational-ledger",
        conversation_id,
        operation,
        str(risk.get("level")),
        str(tool.get("required_tool") or ""),
        str(idempotency_record.get("key") or ""),
        timestamp,
    )
    record = {
        "contract": "operational_audit_ledger_record.v1",
        "component": "operational_audit_ledger",
        "mode": "shadow",
        "passive": True,
        "persistent": False,
        "mutates_state": False,
        "changes_response": False,
        "executes_tools": False,
        "ledger_id": ledger_id,
        "conversation_id": conversation_id,
        "timestamp": timestamp,
        "selected_work": deepcopy(dict(selected_work)),
        "governance_decision": {
            "execution_allowed": bool(governance_assessment.get("execution_allowed")),
            "execution_blocked": bool(governance_assessment.get("execution_blocked")),
            "recommended_execution": governance_assessment.get("recommended_execution"),
            "missing_preconditions": deepcopy(list(governance_assessment.get("missing_preconditions") or [])),
        },
        "risk": deepcopy(dict(risk)),
        "preconditions": preconditions,
        "evidence": evidence,
        "tool": {
            "required": bool(tool.get("required_tool")),
            "name": str(tool.get("required_tool") or ""),
            "capability": str(tool.get("required_capability") or ""),
            "available": bool(tool.get("available", True)),
            "contract": deepcopy(dict(_mapping(tool.get("contract")))),
        },
        "projected_request": projected_request,
        "idempotency": idempotency_record,
        "confirmation_status": confirmation,
        "approval_status": approval,
        "execution_status": execution_status,
        "external_receipt": external_receipt,
        "compensation_strategy": compensation,
        "duplicate_detection": duplicate,
        "replay_safety": _replay_safety(
            idempotency_record=idempotency_record,
            tool=tool,
            external_receipt=external_receipt,
            execution_status=execution_status,
        ),
        "audit_trail": audit_trail,
        "completeness": _completeness(
            ledger_id=ledger_id,
            conversation_id=conversation_id,
            timestamp=timestamp,
            selected_work=selected_work,
            governance_assessment=governance_assessment,
            projected_request=projected_request,
            audit_trail=audit_trail,
            idempotency_record=idempotency_record,
            external_receipt=external_receipt,
            compensation=compensation,
        ),
        "source_inputs": {
            "candidate_work": bool(mapped_work.get("candidate_work")),
            "case_state_projection": bool(mapped_work.get("case_state_projection")),
            "governance_assessment": bool(governance_assessment),
            "execution_plan": bool(execution_plan),
            "runtime_outcomes": len(runtime_outcomes),
            "tool_contract_count": len(tool_contracts),
        },
    }
    return record


def compare_ledger_to_expected(
    ledger_record: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    completeness = _mapping(ledger_record.get("completeness"))
    audit = list(ledger_record.get("audit_trail") or [])
    idempotency = _mapping(ledger_record.get("idempotency"))
    receipt = _mapping(ledger_record.get("external_receipt"))
    compensation = _mapping(ledger_record.get("compensation_strategy"))
    replay = _mapping(ledger_record.get("replay_safety"))
    duplicate = _mapping(ledger_record.get("duplicate_detection"))
    execution = _mapping(ledger_record.get("execution_status"))
    expected_status = str(expected.get("execution_status") or "")
    checks = {
        "ledger_completeness_match": bool(completeness.get("complete")) == bool(expected.get("complete", True)),
        "audit_trace_complete_match": _audit_trace_complete(audit) == bool(expected.get("audit_trace_complete", True)),
        "idempotency_coverage_match": bool(idempotency.get("covered")) == bool(expected.get("idempotency_covered", True)),
        "receipt_coverage_match": bool(receipt.get("covered")) == bool(expected.get("receipt_covered", True)),
        "compensation_coverage_match": bool(compensation.get("covered")) == bool(expected.get("compensation_covered", True)),
        "replay_safety_match": bool(replay.get("safe")) == bool(expected.get("replay_safe", True)),
        "duplicate_detection_match": bool(duplicate.get("duplicate_detected")) == bool(expected.get("duplicate_detected", False)),
        "execution_status_match": not expected_status or str(execution.get("state") or "") == expected_status,
    }
    score = sum(1 for value in checks.values() if value)
    return {
        "contract": "operational_audit_ledger_comparison.v1",
        "checks": checks,
        "score": score,
        "max_score": len(checks),
        "passed": score == len(checks),
        "expected": dict(expected),
        "actual": {
            "complete": completeness.get("complete"),
            "audit_trace_complete": _audit_trace_complete(audit),
            "idempotency_covered": idempotency.get("covered"),
            "receipt_covered": receipt.get("covered"),
            "compensation_covered": compensation.get("covered"),
            "replay_safe": replay.get("safe"),
            "duplicate_detected": duplicate.get("duplicate_detected"),
            "execution_status": execution.get("state"),
        },
    }


def finalize_operational_audit_ledger(
    ledger_record: Mapping[str, Any],
    *,
    tool_result: Any,
) -> dict[str, Any]:
    """Attach a real tool execution result to a projected ledger record."""

    record = deepcopy(dict(ledger_record))
    evidence = _mapping(getattr(tool_result, "evidence", {}))
    execution = _mapping(getattr(tool_result, "execution", {}))
    receipt = _mapping(evidence.get("external_receipt") or evidence.get("projected_receipt"))
    tool_request = _mapping(evidence.get("tool_request") or evidence.get("projected_request"))
    tool_response = _mapping(evidence.get("tool_response") or evidence.get("projected_response"))
    tool_name = str(getattr(tool_result, "tool_name", "") or execution.get("tool_name") or _mapping(record.get("tool")).get("name") or "")
    receipt_valid = bool(receipt.get("receipt_id")) and str(receipt.get("status") or "") not in {"invalid_receipt"}
    success = bool(getattr(tool_result, "success", False)) and receipt_valid
    execution_state = _production_execution_state(
        success=success,
        receipt=receipt,
        tool_error=str(getattr(tool_result, "error", "") or ""),
    )
    record.update(
        {
            "mode": "production",
            "passive": False,
            "persistent": False,
            "executes_tools": bool(execution.get("executed")),
            "tool": {
                **_mapping(record.get("tool")),
                "name": tool_name,
                "available": bool(tool_name),
                "contract": deepcopy(_mapping(execution.get("execution_contract"))),
            },
            "tool_request": deepcopy(tool_request),
            "tool_response": deepcopy(tool_response),
            "external_receipt": deepcopy(receipt),
            "execution_status": {
                "state": execution_state,
                "executed": bool(execution.get("executed")),
                "shadow_only": False,
                "retryable": execution_state in {"tool_timeout", "tool_unavailable"},
                "success": success,
                "reason": _production_execution_reason(execution_state),
                "tool_error": str(getattr(tool_result, "error", "") or ""),
            },
        }
    )
    record["idempotency"] = {
        **_mapping(record.get("idempotency")),
        "key": str(receipt.get("idempotency_key") or _mapping(record.get("idempotency")).get("key") or ""),
        "covered": bool(receipt.get("idempotency_key") or _mapping(record.get("idempotency")).get("covered")),
    }
    record["replay_safety"] = {
        **_mapping(record.get("replay_safety")),
        "safe": bool(record["idempotency"].get("covered")) and bool(receipt.get("replayable", True)),
        "supports_replay": bool(receipt.get("replayable", True)),
        "receipt_status": receipt.get("status"),
        "reason": "production_receipt_replayable" if receipt.get("replayable", True) else "production_receipt_not_replayable",
    }
    record["compensation_strategy"] = {
        **_mapping(record.get("compensation_strategy")),
        "covered": bool(receipt.get("reversible", False)) or bool(_mapping(record.get("compensation_strategy")).get("covered")),
        "status": "covered" if receipt.get("reversible", False) else _mapping(record.get("compensation_strategy")).get("status", "not_required"),
        "strategy": receipt.get("compensation_action") or _mapping(record.get("compensation_strategy")).get("strategy"),
        "execution_state": execution_state,
    }
    record["audit_trail"] = list(record.get("audit_trail") or []) + [
        {
            "event": "tool_executed",
            "source": "tool_engine",
            "tool": tool_name,
            "success": bool(getattr(tool_result, "success", False)),
            "execution_state": execution_state,
        },
        {
            "event": "external_receipt_received",
            "source": tool_name or "tool_engine",
            "status": receipt.get("status"),
            "receipt_id_present": bool(receipt.get("receipt_id")),
        },
    ]
    record["completeness"] = _production_completeness(record)
    return record


def _conversation_id(mapped_work: Mapping[str, Any], ledger_context: Mapping[str, Any]) -> str:
    if ledger_context.get("conversation_id"):
        return str(ledger_context["conversation_id"])
    snapshot = _mapping(mapped_work.get("source_snapshot"))
    if snapshot.get("conversation_id"):
        return str(snapshot["conversation_id"])
    runtime = _mapping(_mapping(snapshot.get("facts")).get("conversation_state_runtime"))
    if runtime.get("conversation_id"):
        return str(runtime["conversation_id"])
    return "shadow_conversation_unknown"


def _timestamp(runtime_outcomes: Sequence[Mapping[str, Any]], ledger_context: Mapping[str, Any]) -> str:
    if ledger_context.get("timestamp"):
        return str(ledger_context["timestamp"])
    for outcome in runtime_outcomes:
        mapped = _mapping(outcome)
        if mapped.get("started_at"):
            return str(mapped["started_at"])
        if mapped.get("finished_at"):
            return str(mapped["finished_at"])
    return "shadow_timestamp_not_available"


def _confirmation_status(governance: Mapping[str, Any], ledger_context: Mapping[str, Any]) -> dict[str, Any]:
    required = bool(governance.get("requires_confirmation"))
    rejected = bool(ledger_context.get("confirmation_rejected"))
    present = bool(ledger_context.get("user_confirmation")) and not rejected
    if not required:
        status = "not_required"
    elif rejected:
        status = "rejected"
    elif present:
        status = "confirmed"
    else:
        status = "missing"
    return {"required": required, "present": present, "status": status}


def _approval_status(governance: Mapping[str, Any], ledger_context: Mapping[str, Any]) -> dict[str, Any]:
    required = bool(governance.get("requires_human_approval"))
    rejected = bool(ledger_context.get("approval_rejected"))
    present = bool(ledger_context.get("human_approval")) and not rejected
    if not required:
        status = "not_required"
    elif rejected:
        status = "rejected"
    elif present:
        status = "approved"
    else:
        status = "missing"
    return {"required": required, "present": present, "status": status}


def _idempotency_record(
    *,
    operation: str,
    conversation_id: str,
    tool: Mapping[str, Any],
    idempotency: Mapping[str, Any],
    ledger_context: Mapping[str, Any],
) -> dict[str, Any]:
    required = bool(idempotency.get("required"))
    guarantee = str(idempotency.get("guarantee") or "")
    supplied = ledger_context.get("idempotency_key")
    if supplied:
        key = str(supplied)
        source = "ledger_context"
    elif required and guarantee == "idempotent":
        key = _stable_id("idempotent", conversation_id, operation, str(tool.get("required_tool") or ""))
        source = "derived_from_existing_inputs"
    else:
        key = ""
        source = "missing"
    covered = not required or bool(key)
    return {
        "required": required,
        "covered": covered,
        "guarantee": guarantee or "not_required",
        "key": key,
        "source": source,
    }


def _duplicate_detection(
    *,
    operation: str,
    tool: Mapping[str, Any],
    idempotency_record: Mapping[str, Any],
    ledger_context: Mapping[str, Any],
) -> dict[str, Any]:
    key = str(idempotency_record.get("key") or "")
    previous = list(ledger_context.get("previous_ledger_records") or [])
    for record in previous:
        mapped = _mapping(record)
        previous_idempotency = _mapping(mapped.get("idempotency"))
        previous_tool = _mapping(mapped.get("tool"))
        previous_work = _mapping(mapped.get("selected_work"))
        if not key or previous_idempotency.get("key") != key:
            continue
        if previous_work.get("operation") == operation and previous_tool.get("name") == tool.get("required_tool"):
            return {
                "checked": True,
                "duplicate_detected": True,
                "duplicate_of": mapped.get("ledger_id"),
                "reason": "same_operation_tool_and_idempotency_key",
            }
    return {
        "checked": bool(key),
        "duplicate_detected": False,
        "duplicate_of": None,
        "reason": "no_prior_matching_idempotency_key" if key else "idempotency_key_unavailable",
    }


def _projected_request(
    *,
    operation: str,
    selected_work: Mapping[str, Any],
    governance_assessment: Mapping[str, Any],
    tool: Mapping[str, Any],
    execution_plan: Mapping[str, Any],
) -> dict[str, Any]:
    required_tool = str(tool.get("required_tool") or "")
    allowed = bool(governance_assessment.get("execution_allowed"))
    if not required_tool:
        status = "not_required"
    elif allowed:
        status = "would_send_if_execution_enabled"
    else:
        status = "blocked_before_send"
    return {
        "status": status,
        "tool": required_tool,
        "operation": operation,
        "payload_projection": {
            "contains_raw_payload": False,
            "evidence_refs": list(governance_assessment.get("required_evidence") or []),
            "selected_work_ref": selected_work.get("operation"),
            "execution_flow": execution_plan.get("flow"),
        },
    }


def _external_receipt(
    *,
    governance_assessment: Mapping[str, Any],
    ledger_context: Mapping[str, Any],
) -> dict[str, Any]:
    supplied = _mapping(ledger_context.get("shadow_external_receipt"))
    if supplied:
        status = str(supplied.get("status") or "shadow_receipt")
        return {
            "covered": True,
            "shadow": True,
            "status": status,
            "receipt_id": str(supplied.get("receipt_id") or ""),
            "external_status": str(supplied.get("external_status") or status),
            "source": "ledger_context_shadow_receipt",
        }
    if governance_assessment.get("execution_allowed"):
        return {
            "covered": True,
            "shadow": True,
            "status": "not_created_shadow",
            "receipt_id": "",
            "external_status": "not_executed",
            "source": "shadow_no_execution",
        }
    return {
        "covered": True,
        "shadow": True,
        "status": "not_applicable_blocked",
        "receipt_id": "",
        "external_status": "blocked_before_execution",
        "source": "governance_blocked",
    }


def _execution_status(
    *,
    governance_assessment: Mapping[str, Any],
    approval: Mapping[str, Any],
    confirmation: Mapping[str, Any],
    duplicate: Mapping[str, Any],
    external_receipt: Mapping[str, Any],
    ledger_context: Mapping[str, Any],
) -> dict[str, Any]:
    requested = str(ledger_context.get("shadow_execution_event") or "")
    receipt_status = str(external_receipt.get("status") or "")
    if duplicate.get("duplicate_detected"):
        state = "duplicate_detected_shadow"
    elif confirmation.get("status") == "rejected":
        state = "cancelled_by_user_confirmation"
    elif approval.get("status") == "rejected":
        state = "blocked_by_approval_rejected"
    elif requested == "cancelled":
        state = "cancelled_before_execution"
    elif receipt_status in {"timeout", "partial_response", "tool_down"}:
        state = f"shadow_{receipt_status}"
    elif governance_assessment.get("manual_only"):
        state = "manual_only"
    elif not governance_assessment.get("execution_allowed"):
        state = "blocked_by_governance"
    else:
        state = "would_execute"
    retryable = state in {"shadow_timeout", "shadow_tool_down", "duplicate_detected_shadow"}
    return {
        "state": state,
        "executed": False,
        "shadow_only": True,
        "retryable": retryable,
        "reason": _execution_reason(state),
    }


def _compensation_strategy(
    *,
    governance_assessment: Mapping[str, Any],
    execution_status: Mapping[str, Any],
) -> dict[str, Any]:
    reversibility = _mapping(governance_assessment.get("reversibility"))
    risk = _mapping(governance_assessment.get("risk"))
    if int(risk.get("level") or 0) <= 1:
        status = "not_required"
        strategy = "no_external_state_change"
    elif reversibility.get("reversible"):
        status = "covered"
        strategy = "compensating_action_or_reversal_required_if_executed"
    else:
        status = "manual_control_required"
        strategy = "not_reversible_keep_manual_or_require_human_control"
    return {
        "covered": bool(status),
        "status": status,
        "strategy": strategy,
        "execution_state": execution_status.get("state"),
    }


def _evidence_record(mapped_work: Mapping[str, Any], governance_assessment: Mapping[str, Any]) -> dict[str, Any]:
    candidate = _mapping(_mapping(governance_assessment.get("source")).get("candidate"))
    return {
        "available_evidence": list(governance_assessment.get("available_evidence") or []),
        "candidate_evidence": deepcopy(dict(_mapping(candidate.get("evidence")))),
        "case_state_stage": _mapping(mapped_work.get("case_state_projection")).get("case_stage"),
        "contains_raw_payload": False,
    }


def _preconditions(governance_assessment: Mapping[str, Any]) -> dict[str, Any]:
    missing = list(governance_assessment.get("missing_preconditions") or [])
    return {
        "status": "passed" if not missing else "missing",
        "missing": deepcopy(missing),
        "required_evidence": list(governance_assessment.get("required_evidence") or []),
        "audit_requirements": list(governance_assessment.get("audit_requirements") or []),
    }


def _replay_safety(
    *,
    idempotency_record: Mapping[str, Any],
    tool: Mapping[str, Any],
    external_receipt: Mapping[str, Any],
    execution_status: Mapping[str, Any],
) -> dict[str, Any]:
    contract = _mapping(tool.get("contract"))
    replay_supported = bool(contract.get("supports_replay", False))
    low_risk_no_tool = not tool.get("required_tool")
    retryable = bool(execution_status.get("retryable"))
    safe = bool(low_risk_no_tool or (idempotency_record.get("covered") and (replay_supported or not retryable)))
    return {
        "safe": safe,
        "supports_replay": replay_supported,
        "retryable": retryable,
        "receipt_status": external_receipt.get("status"),
        "reason": "safe_replay_or_no_tool" if safe else "unsafe_without_idempotency_or_replay",
    }


def _audit_trail(
    *,
    selected_work: Mapping[str, Any],
    governance_assessment: Mapping[str, Any],
    projected_request: Mapping[str, Any],
    execution_status: Mapping[str, Any],
    external_receipt: Mapping[str, Any],
    duplicate: Mapping[str, Any],
) -> list[dict[str, Any]]:
    events = [
        {"event": "selected_work_observed", "source": "candidate_work", "operation": selected_work.get("operation")},
        {
            "event": "governance_assessed",
            "source": "operational_governance_gate",
            "allowed": governance_assessment.get("execution_allowed"),
            "risk_level": _mapping(governance_assessment.get("risk")).get("level"),
        },
        {"event": "request_projected", "source": "operational_audit_ledger", "status": projected_request.get("status")},
        {"event": "duplicate_checked", "source": "operational_audit_ledger", "duplicate": duplicate.get("duplicate_detected")},
        {"event": "execution_not_performed_shadow", "source": "operational_audit_ledger", "state": execution_status.get("state")},
        {"event": "receipt_projected", "source": "operational_audit_ledger", "status": external_receipt.get("status")},
    ]
    return events


def _completeness(
    *,
    ledger_id: str,
    conversation_id: str,
    timestamp: str,
    selected_work: Mapping[str, Any],
    governance_assessment: Mapping[str, Any],
    projected_request: Mapping[str, Any],
    audit_trail: Sequence[Mapping[str, Any]],
    idempotency_record: Mapping[str, Any],
    external_receipt: Mapping[str, Any],
    compensation: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "ledger_id": ledger_id,
        "conversation_id": conversation_id,
        "timestamp": timestamp,
        "selected_work": selected_work.get("operation"),
        "governance_decision": governance_assessment.get("recommended_execution"),
        "projected_request": projected_request.get("status"),
        "audit_trail": audit_trail,
        "idempotency": idempotency_record.get("covered") is not None,
        "external_receipt": external_receipt.get("status"),
        "compensation_strategy": compensation.get("status"),
    }
    missing = [name for name, value in required.items() if _missing(value)]
    return {
        "complete": not missing,
        "missing_fields": missing,
        "field_count": len(required),
        "covered_field_count": len(required) - len(missing),
    }


def _audit_trace_complete(audit: Sequence[Mapping[str, Any]]) -> bool:
    events = {str(_mapping(item).get("event") or "") for item in audit}
    return {
        "selected_work_observed",
        "governance_assessed",
        "request_projected",
        "execution_not_performed_shadow",
        "receipt_projected",
    }.issubset(events)


def _execution_reason(state: str) -> str:
    return {
        "duplicate_detected_shadow": "same idempotency key was already observed",
        "cancelled_by_user_confirmation": "user confirmation was rejected",
        "blocked_by_approval_rejected": "human approval was rejected",
        "cancelled_before_execution": "operation was cancelled before execution",
        "shadow_timeout": "shadow receipt represents timeout",
        "shadow_partial_response": "shadow receipt represents partial response",
        "shadow_tool_down": "shadow receipt represents tool outage",
        "manual_only": "operation is not eligible for automatic execution",
        "blocked_by_governance": "governance preconditions are not satisfied",
        "would_execute": "governance would allow execution if execution were enabled",
    }.get(state, "shadow_execution_status")


def _production_execution_state(
    *,
    success: bool,
    receipt: Mapping[str, Any],
    tool_error: str,
) -> str:
    status = str(receipt.get("status") or "")
    external_status = str(receipt.get("external_status") or "")
    if status == "duplicate_replayed" or external_status == "duplicate_replayed":
        return "duplicate_replayed"
    if success:
        return "executed"
    if status == "timeout" or "timed out" in tool_error.lower():
        return "tool_timeout"
    if status == "tool_down" or "unavailable" in tool_error.lower():
        return "tool_unavailable"
    if status == "invalid_receipt" or not receipt.get("receipt_id"):
        return "invalid_receipt"
    return "tool_error"


def _production_execution_reason(state: str) -> str:
    return {
        "executed": "real operational tool completed and returned a valid receipt",
        "duplicate_replayed": "idempotency key matched an existing operation and the stored receipt was replayed",
        "tool_timeout": "real operational tool did not complete before timeout",
        "tool_unavailable": "real operational tool was unavailable",
        "invalid_receipt": "tool response did not include a valid external receipt",
        "tool_error": "real operational tool returned an execution error",
    }.get(state, "real operational execution status recorded")


def _production_completeness(record: Mapping[str, Any]) -> dict[str, Any]:
    receipt = _mapping(record.get("external_receipt"))
    execution = _mapping(record.get("execution_status"))
    required = {
        "ledger_id": record.get("ledger_id"),
        "conversation_id": record.get("conversation_id"),
        "timestamp": record.get("timestamp"),
        "selected_work": _mapping(record.get("selected_work")).get("operation"),
        "governance_decision": _mapping(record.get("governance_decision")).get("recommended_execution"),
        "tool_executed": _mapping(record.get("tool")).get("name"),
        "request": record.get("tool_request"),
        "response": record.get("tool_response"),
        "external_receipt": receipt.get("status"),
        "idempotency_key": _mapping(record.get("idempotency")).get("key"),
        "execution_status": execution.get("state"),
    }
    missing = [name for name, value in required.items() if _missing(value)]
    return {
        "complete": not missing,
        "missing_fields": missing,
        "field_count": len(required),
        "covered_field_count": len(required) - len(missing),
    }


def _stable_id(*parts: str) -> str:
    payload = json.dumps([str(part) for part in parts], sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()[:24]


def _missing(value: Any) -> bool:
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
