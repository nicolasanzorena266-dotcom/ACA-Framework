from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence


RISK_LEVELS: dict[int, dict[str, str]] = {
    0: {"name": "inform", "description": "No external state change."},
    1: {"name": "prepare", "description": "Prepare internal work without external writes."},
    2: {"name": "internal_reversible_write", "description": "Write reversible internal state."},
    3: {"name": "external_side_effect", "description": "Create or modify state in an external system."},
    4: {"name": "irreversible_or_high_liability", "description": "High-impact or irreversible action."},
}


_OPERATION_PROFILES: dict[str, dict[str, Any]] = {
    "explain_domain_concept": {"level": 0, "operation_type": "informative"},
    "explain_documentation_requirements": {"level": 0, "operation_type": "informative"},
    "explain_current_step_simpler": {"level": 0, "operation_type": "informative"},
    "provide_repair_risk_guidance": {"level": 0, "operation_type": "protective"},
    "close_case_no_action": {"level": 0, "operation_type": "administrative"},
    "no_operational_work_identified": {"level": 0, "operation_type": "none"},
    "block_real_status_lookup": {
        "level": 0,
        "operation_type": "protective",
        "blocked_real_capability": "insurance.claim_status.lookup",
    },
    "block_document_upload": {
        "level": 0,
        "operation_type": "protective",
        "blocked_real_capability": "insurance.document.upload",
    },
    "collect_claim_blocker": {"level": 1, "operation_type": "evidence_gathering"},
    "request_billing_line_item": {"level": 1, "operation_type": "evidence_gathering"},
    "request_rejection_detail": {"level": 1, "operation_type": "evidence_gathering"},
    "diagnose_connectivity_issue": {"level": 1, "operation_type": "evidence_gathering"},
    "continue_conversation_plan": {"level": 1, "operation_type": "administrative"},
    "start_claim_guidance": {"level": 1, "operation_type": "administrative"},
    "repair_service_interaction": {"level": 1, "operation_type": "recovery"},
    "prepare_claim_follow_up": {"level": 1, "operation_type": "preparatory"},
    "prepare_documentation_review": {"level": 1, "operation_type": "preparatory"},
    "prepare_billing_review": {"level": 1, "operation_type": "preparatory"},
    "prepare_outage_follow_up": {"level": 1, "operation_type": "preparatory"},
    "prepare_technical_visit": {"level": 1, "operation_type": "preparatory"},
    "prepare_handoff": {"level": 1, "operation_type": "preparatory"},
    "prepare_case_summary": {"level": 1, "operation_type": "preparatory"},
    "save_internal_case_note": {
        "level": 2,
        "operation_type": "administrative",
        "required_tool": "internal_case_notes",
        "required_evidence": ("case_reference", "summary"),
        "reversible": True,
    },
    "mark_internal_checklist_item": {
        "level": 2,
        "operation_type": "administrative",
        "required_tool": "internal_case_checklist",
        "required_evidence": ("case_reference", "checklist_item"),
        "reversible": True,
    },
    "real_claim_status_lookup": {
        "level": 3,
        "operation_type": "external_lookup",
        "capability": "insurance.claim_status.lookup",
        "required_tool": "claim_status_lookup",
        "required_evidence": ("case_reference",),
        "reversible": False,
    },
    "associate_documentation": {
        "level": 3,
        "operation_type": "external_write",
        "capability": "insurance.document.upload",
        "required_tool": "document_association",
        "required_evidence": ("case_reference", "documents"),
        "reversible": True,
    },
    "open_ticket": {
        "level": 3,
        "operation_type": "external_write",
        "required_tool": "ticket_create",
        "required_evidence": ("issue_summary",),
        "reversible": True,
    },
    "schedule_technical_visit": {
        "level": 3,
        "operation_type": "coordinative",
        "required_tool": "technical_visit_scheduler",
        "required_evidence": ("technical_diagnosis", "service_address"),
        "reversible": True,
    },
    "request_callback": {
        "level": 3,
        "operation_type": "coordinative",
        "required_tool": "callback_request",
        "required_evidence": ("contact_channel", "issue_summary"),
        "reversible": True,
    },
    "execute_handoff": {
        "level": 3,
        "operation_type": "escalation",
        "required_tool": "handoff_dispatch",
        "required_evidence": ("case_summary", "target_owner"),
        "reversible": False,
    },
    "apply_service_credit": {
        "level": 4,
        "operation_type": "resolutive",
        "required_tool": "billing_credit_apply",
        "required_evidence": ("account_reference", "credit_reason"),
        "requires_human_approval": True,
        "manual_only": True,
        "reversible": False,
        "regulatory_constraints": ("financial_adjustment",),
    },
    "modify_invoice": {
        "level": 4,
        "operation_type": "resolutive",
        "required_tool": "invoice_modify",
        "required_evidence": ("invoice_id", "discrepancy_evidence"),
        "requires_human_approval": True,
        "manual_only": True,
        "reversible": False,
        "regulatory_constraints": ("billing_record_mutation",),
    },
    "change_account_holder": {
        "level": 4,
        "operation_type": "identity_sensitive",
        "required_tool": "account_holder_change",
        "required_evidence": ("verified_identity", "legal_authorization"),
        "requires_human_approval": True,
        "manual_only": True,
        "reversible": False,
        "regulatory_constraints": ("identity_verification", "account_ownership"),
    },
    "cancel_service": {
        "level": 4,
        "operation_type": "irreversible",
        "required_tool": "service_cancel",
        "required_evidence": ("verified_identity", "cancellation_confirmation"),
        "requires_human_approval": True,
        "manual_only": True,
        "reversible": False,
        "regulatory_constraints": ("service_termination",),
    },
}


def assess_operational_governance(
    mapped_work: Mapping[str, Any],
    *,
    plugin_manifests: Sequence[Mapping[str, Any]] = (),
    tool_contracts: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any] | None = None,
    execution_plan: Mapping[str, Any] | None = None,
    runtime_outcomes: Sequence[Mapping[str, Any]] = (),
    governance_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Audit whether already-selected work would be executable in production.

    The gate is a shadow projection. It never selects work, calls tools, mutates
    state or changes the response.
    """

    tool_contracts = dict(tool_contracts or {})
    governance_context = dict(governance_context or {})
    selected = _mapping(mapped_work.get("selected_work"))
    operation = str(selected.get("operation") or "no_operational_work_identified")
    category = str(selected.get("category") or mapped_work.get("operational_category") or "")
    expected_outcome = str(selected.get("expected_outcome") or mapped_work.get("expected_outcome") or "")
    profile = _profile_for(operation, category=category, expected_outcome=expected_outcome)
    risk_level = int(profile.get("level", 1))
    risk = {"level": risk_level, **RISK_LEVELS.get(risk_level, RISK_LEVELS[1])}
    candidate = _candidate_for_operation(mapped_work, operation)
    case_state = _mapping(mapped_work.get("case_state_projection"))
    required_tool = str(profile.get("required_tool") or "")
    capability = str(profile.get("capability") or _capability_from_blockers(candidate, mapped_work) or "")
    tool_availability = _tool_availability(
        required_tool=required_tool,
        capability=capability,
        tool_contracts=tool_contracts,
        plugin_manifests=plugin_manifests,
        mapped_work=mapped_work,
    )
    evidence_assessment = _evidence_assessment(
        profile=profile,
        mapped_work=mapped_work,
        candidate=candidate,
        case_state=case_state,
        governance_context=governance_context,
    )
    requires_confirmation = bool(profile.get("requires_confirmation", risk_level >= 2))
    requires_human_approval = bool(profile.get("requires_human_approval", risk_level >= 4))
    manual_only = bool(profile.get("manual_only", False))
    confirmation_present = bool(governance_context.get("user_confirmation"))
    human_approval_present = bool(governance_context.get("human_approval"))
    idempotency = _idempotency_assessment(
        risk_level=risk_level,
        tool_availability=tool_availability,
        governance_context=governance_context,
    )
    permissions = _permission_assessment(
        operation=operation,
        risk_level=risk_level,
        profile=profile,
        governance_context=governance_context,
    )
    reversibility = _reversibility_assessment(profile, risk_level=risk_level)
    missing_preconditions = list(evidence_assessment["missing_evidence"])
    if not permissions["allowed"]:
        missing_preconditions.append(permissions["missing"])
    if required_tool and not tool_availability["available"]:
        missing_preconditions.append(
            {
                "type": "tool_unavailable",
                "tool": required_tool,
                "capability": capability,
                "reason": tool_availability["reason"],
            }
        )
    if requires_confirmation and not confirmation_present:
        missing_preconditions.append({"type": "confirmation_required", "reason": "user_confirmation_not_captured"})
    if requires_human_approval and not human_approval_present:
        missing_preconditions.append({"type": "human_approval_required", "reason": "human_approval_not_captured"})
    if idempotency["missing"]:
        missing_preconditions.append(idempotency["missing"])
    if manual_only:
        missing_preconditions.append({"type": "manual_only", "reason": "operation_not_eligible_for_automatic_execution"})

    regulatory_constraints = list(profile.get("regulatory_constraints") or [])
    if regulatory_constraints and not human_approval_present:
        missing_preconditions.append(
            {
                "type": "regulatory_control_required",
                "constraints": regulatory_constraints,
                "reason": "regulated_operation_requires_human_governance",
            }
        )

    execution_allowed = not missing_preconditions and not manual_only
    execution_blocked = not execution_allowed
    recommendation = _recommendation(
        risk_level=risk_level,
        execution_allowed=execution_allowed,
        requires_confirmation=requires_confirmation,
        requires_human_approval=requires_human_approval,
        manual_only=manual_only,
    )
    audit_requirements = _audit_requirements(risk_level, requires_human_approval=requires_human_approval)
    reasoning = _reasoning(
        operation=operation,
        risk=risk,
        execution_allowed=execution_allowed,
        tool_availability=tool_availability,
        evidence_assessment=evidence_assessment,
        requires_confirmation=requires_confirmation,
        requires_human_approval=requires_human_approval,
        missing_preconditions=missing_preconditions,
    )
    return {
        "contract": "operational_governance_assessment.v1",
        "component": "operational_governance_gate",
        "mode": "shadow",
        "passive": True,
        "mutates_state": False,
        "changes_response": False,
        "executes_tools": False,
        "selected_work": {
            "operation": operation,
            "category": category,
            "expected_outcome": expected_outcome,
            "confidence": selected.get("confidence"),
        },
        "risk": risk,
        "operation_type": str(profile.get("operation_type") or category or "unknown"),
        "execution_allowed": execution_allowed,
        "execution_blocked": execution_blocked,
        "recommended_execution": recommendation,
        "requires_confirmation": requires_confirmation,
        "requires_human_approval": requires_human_approval,
        "manual_only": manual_only,
        "required_evidence": list(profile.get("required_evidence") or []),
        "available_evidence": evidence_assessment["available_evidence"],
        "missing_preconditions": missing_preconditions,
        "tool_availability": tool_availability,
        "permissions": permissions,
        "idempotency": idempotency,
        "reversibility": reversibility,
        "audit_requirements": audit_requirements,
        "regulatory_constraints": regulatory_constraints,
        "blocked_real_capability": profile.get("blocked_real_capability"),
        "reasoning": reasoning,
        "observed_inputs": {
            "candidate_work": bool(mapped_work.get("candidate_work")),
            "case_state_projection": bool(case_state),
            "execution_plan": bool(execution_plan or mapped_work.get("evidence", {}).get("runtime_flow")),
            "policy": bool(policy or _policy_from_mapped_work(mapped_work)),
            "runtime_outcomes": len(runtime_outcomes or []),
            "tool_contract_count": len(tool_contracts),
            "plugin_manifest_count": len(plugin_manifests),
        },
        "source": {
            "candidate": deepcopy(candidate),
            "case_stage": case_state.get("case_stage"),
            "policy": deepcopy(dict(policy or _policy_from_mapped_work(mapped_work))),
        },
    }


def compare_governance_to_expected(
    assessment: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    risk = _mapping(assessment.get("risk"))
    tool = _mapping(assessment.get("tool_availability"))
    idempotency = _mapping(assessment.get("idempotency"))
    missing = list(assessment.get("missing_preconditions") or [])
    expected_missing = [str(item) for item in expected.get("missing_preconditions_contains") or []]
    missing_types = {str(_mapping(item).get("type") or "") for item in missing}
    checks = {
        "risk_level_match": int(risk.get("level", -1)) == int(expected.get("risk_level", -999)),
        "execution_allowed_match": bool(assessment.get("execution_allowed")) == bool(expected.get("execution_allowed")),
        "execution_blocked_match": bool(assessment.get("execution_blocked")) == bool(expected.get("execution_blocked", not bool(expected.get("execution_allowed")))),
        "confirmation_match": bool(assessment.get("requires_confirmation")) == bool(expected.get("requires_confirmation")),
        "human_approval_match": bool(assessment.get("requires_human_approval")) == bool(expected.get("requires_human_approval")),
        "tool_availability_match": bool(tool.get("available")) == bool(expected.get("tool_available", not bool(_mapping(tool).get("required_tool")))),
        "idempotency_match": bool(idempotency.get("safe")) == bool(expected.get("idempotency_safe", True)),
        "missing_preconditions_match": all(item in missing_types for item in expected_missing),
    }
    score = sum(1 for value in checks.values() if value)
    return {
        "contract": "operational_governance_comparison.v1",
        "checks": checks,
        "score": score,
        "max_score": len(checks),
        "passed": score == len(checks),
        "expected": dict(expected),
        "actual": {
            "risk_level": risk.get("level"),
            "execution_allowed": assessment.get("execution_allowed"),
            "execution_blocked": assessment.get("execution_blocked"),
            "requires_confirmation": assessment.get("requires_confirmation"),
            "requires_human_approval": assessment.get("requires_human_approval"),
            "tool_available": tool.get("available"),
            "idempotency_safe": idempotency.get("safe"),
            "missing_precondition_types": sorted(missing_types),
        },
    }


def _profile_for(operation: str, *, category: str, expected_outcome: str) -> dict[str, Any]:
    if operation in _OPERATION_PROFILES:
        return dict(_OPERATION_PROFILES[operation])
    if category in {"informative", "protective"} or expected_outcome in {"explained", "blocked", "unsafe_operation", "no_action_required"}:
        return {"level": 0, "operation_type": category or "informative"}
    if category in {"preparatory", "administrative", "escalation"}:
        return {"level": 1, "operation_type": category}
    return {"level": 2, "operation_type": category or "unknown", "required_evidence": ("operation_evidence",)}


def _candidate_for_operation(mapped_work: Mapping[str, Any], operation: str) -> dict[str, Any]:
    for candidate in mapped_work.get("candidate_work") or []:
        mapped = _mapping(candidate)
        if str(mapped.get("operation") or "") == operation:
            return mapped
    return _mapping(mapped_work.get("selected_work"))


def _tool_availability(
    *,
    required_tool: str,
    capability: str,
    tool_contracts: Mapping[str, Any],
    plugin_manifests: Sequence[Mapping[str, Any]],
    mapped_work: Mapping[str, Any],
) -> dict[str, Any]:
    contract = _mapping(tool_contracts.get(required_tool)) if required_tool else {}
    public_action = _public_action_for_capability(plugin_manifests, capability)
    blocked_capability = bool(capability and _capability_blocked(plugin_manifests, capability))
    blocked_by = list(mapped_work.get("blocked_by") or []) + list(_candidate_for_operation(mapped_work, str(_mapping(mapped_work.get("selected_work")).get("operation") or "")).get("blocked_by") or [])
    blocker_types = {str(_mapping(item).get("type") or "") for item in blocked_by}
    if not required_tool:
        return {
            "required_tool": "",
            "required_capability": capability,
            "available": True,
            "reason": "no_tool_required",
            "contract": {},
            "public_action": public_action,
            "blocked_capability": blocked_capability,
        }
    if blocked_capability:
        return {
            "required_tool": required_tool,
            "required_capability": capability,
            "available": False,
            "reason": "capability_blocked_by_manifest",
            "contract": contract,
            "public_action": public_action,
            "blocked_capability": True,
        }
    if public_action and not bool(public_action.get("enabled", False)):
        return {
            "required_tool": required_tool,
            "required_capability": capability,
            "available": False,
            "reason": "public_action_disabled",
            "contract": contract,
            "public_action": public_action,
            "blocked_capability": False,
        }
    if "missing_real_tool" in blocker_types and not contract:
        return {
            "required_tool": required_tool,
            "required_capability": capability,
            "available": False,
            "reason": "mapped_work_reports_missing_real_tool",
            "contract": contract,
            "public_action": public_action,
            "blocked_capability": blocked_capability,
        }
    if not contract:
        return {
            "required_tool": required_tool,
            "required_capability": capability,
            "available": False,
            "reason": "tool_contract_missing",
            "contract": {},
            "public_action": public_action,
            "blocked_capability": blocked_capability,
        }
    return {
        "required_tool": required_tool,
        "required_capability": capability,
        "available": True,
        "reason": "tool_contract_available",
        "contract": contract,
        "public_action": public_action,
        "blocked_capability": blocked_capability,
    }


def _evidence_assessment(
    *,
    profile: Mapping[str, Any],
    mapped_work: Mapping[str, Any],
    candidate: Mapping[str, Any],
    case_state: Mapping[str, Any],
    governance_context: Mapping[str, Any],
) -> dict[str, Any]:
    required = [str(item) for item in profile.get("required_evidence") or []]
    available = set(str(item) for item in governance_context.get("available_evidence") or [])
    if candidate.get("evidence"):
        available.add("candidate_evidence")
    if case_state.get("available_evidence"):
        available.add("case_state_evidence")
    if case_state.get("claim", {}).get("loaded"):
        available.add("case_reference")
    if case_state.get("documentation", {}).get("state") in {"pending", "unknown_or_pending", "blocked_upload"}:
        available.add("documents")
    if case_state.get("technical_service", {}).get("state") in {"issue_open", "service_down"}:
        available.add("technical_diagnosis")
    if mapped_work.get("selected_work"):
        available.add("operation_evidence")
    missing = [
        {"type": "missing_evidence", "evidence": item, "reason": "required_operational_evidence_not_available"}
        for item in required
        if item not in available
    ]
    return {
        "available_evidence": sorted(available),
        "missing_evidence": missing,
    }


def _idempotency_assessment(
    *,
    risk_level: int,
    tool_availability: Mapping[str, Any],
    governance_context: Mapping[str, Any],
) -> dict[str, Any]:
    if risk_level < 2:
        return {"required": False, "safe": True, "guarantee": "not_required_for_low_risk_operation", "missing": {}}
    if not tool_availability.get("required_tool"):
        return {"required": False, "safe": True, "guarantee": "no_tool_required", "missing": {}}
    contract = _mapping(tool_availability.get("contract"))
    if not contract:
        return {
            "required": True,
            "safe": False,
            "guarantee": "unknown_without_tool_contract",
            "missing": {"type": "idempotency_unknown", "reason": "tool_contract_missing"},
        }
    idempotency = str(contract.get("idempotency") or "unknown")
    if idempotency == "idempotent":
        return {"required": True, "safe": True, "guarantee": idempotency, "missing": {}}
    if idempotency == "requires_idempotency_key":
        if governance_context.get("idempotency_key"):
            return {"required": True, "safe": True, "guarantee": idempotency, "missing": {}}
        return {
            "required": True,
            "safe": False,
            "guarantee": idempotency,
            "missing": {"type": "idempotency_key_required", "reason": "idempotency_key_not_present"},
        }
    return {
        "required": True,
        "safe": False,
        "guarantee": idempotency,
        "missing": {"type": "unsafe_idempotency", "reason": f"idempotency_not_safe:{idempotency}"},
    }


def _permission_assessment(
    *,
    operation: str,
    risk_level: int,
    profile: Mapping[str, Any],
    governance_context: Mapping[str, Any],
) -> dict[str, Any]:
    if risk_level < 2:
        return {"required": False, "allowed": True, "permission": "", "missing": {}}
    required = str(profile.get("required_permission") or f"execute:{operation}")
    permissions = _mapping(governance_context.get("permissions"))
    if permissions.get(required) is True:
        return {"required": True, "allowed": True, "permission": required, "missing": {}}
    return {
        "required": True,
        "allowed": False,
        "permission": required,
        "missing": {
            "type": "permission_insufficient",
            "permission": required,
            "reason": "required_operational_permission_not_present",
        },
    }


def _reversibility_assessment(profile: Mapping[str, Any], *, risk_level: int) -> dict[str, Any]:
    if "reversible" in profile:
        reversible = bool(profile.get("reversible"))
    else:
        reversible = risk_level <= 2
    if risk_level <= 1:
        status = "not_needed"
    elif reversible:
        status = "reversible_or_compensatable"
    else:
        status = "not_reversible"
    return {"reversible": reversible, "status": status}


def _audit_requirements(risk_level: int, *, requires_human_approval: bool) -> list[str]:
    requirements = ["governance_assessment_trace"]
    if risk_level >= 1:
        requirements.append("selected_work_snapshot")
    if risk_level >= 2:
        requirements.extend(["durable_operation_record", "idempotency_record"])
    if risk_level >= 3:
        requirements.extend(["external_correlation_id", "tool_receipt", "retry_policy"])
    if requires_human_approval:
        requirements.append("human_approval_receipt")
    if risk_level >= 4:
        requirements.extend(["compensation_or_manual_control", "regulated_operation_review"])
    return requirements


def _recommendation(
    *,
    risk_level: int,
    execution_allowed: bool,
    requires_confirmation: bool,
    requires_human_approval: bool,
    manual_only: bool,
) -> str:
    if manual_only:
        return "manual_only"
    if execution_allowed:
        return "auto_execute" if risk_level <= 1 else "execute_with_governance"
    if requires_human_approval:
        return "requires_human_approval"
    if requires_confirmation:
        return "requires_confirmation"
    return "blocked_or_shadow_only"


def _reasoning(
    *,
    operation: str,
    risk: Mapping[str, Any],
    execution_allowed: bool,
    tool_availability: Mapping[str, Any],
    evidence_assessment: Mapping[str, Any],
    requires_confirmation: bool,
    requires_human_approval: bool,
    missing_preconditions: Sequence[Mapping[str, Any]],
) -> list[str]:
    reasons = [
        f"operation:{operation}",
        f"risk_level:{risk.get('level')}:{risk.get('name')}",
    ]
    if tool_availability.get("required_tool"):
        reasons.append(f"tool:{tool_availability.get('required_tool')}:{tool_availability.get('reason')}")
    else:
        reasons.append("tool:not_required")
    if evidence_assessment.get("missing_evidence"):
        reasons.append("evidence:missing_required_items")
    else:
        reasons.append("evidence:sufficient_for_shadow_assessment")
    if requires_confirmation:
        reasons.append("confirmation:required")
    if requires_human_approval:
        reasons.append("human_approval:required")
    if missing_preconditions:
        reasons.append("execution:blocking_preconditions_present")
    reasons.append("execution:allowed" if execution_allowed else "execution:not_allowed")
    return reasons


def _capability_from_blockers(candidate: Mapping[str, Any], mapped_work: Mapping[str, Any]) -> str:
    for item in list(candidate.get("blocked_by") or []) + list(mapped_work.get("blocked_by") or []):
        blocker = _mapping(item)
        capability = blocker.get("capability")
        if capability:
            return str(capability)
    return ""


def _public_action_for_capability(
    plugin_manifests: Sequence[Mapping[str, Any]],
    capability: str,
) -> dict[str, Any]:
    if not capability:
        return {}
    for manifest in plugin_manifests:
        for action in _mapping(manifest).get("public_actions") or []:
            mapped = _mapping(action)
            if mapped.get("capability") == capability:
                return mapped
    return {}


def _capability_blocked(plugin_manifests: Sequence[Mapping[str, Any]], capability: str) -> bool:
    if not capability:
        return False
    return any(capability in set(_mapping(manifest).get("blocked_capabilities") or []) for manifest in plugin_manifests)


def _policy_from_mapped_work(mapped_work: Mapping[str, Any]) -> dict[str, Any]:
    evidence = _mapping(mapped_work.get("evidence"))
    decision = evidence.get("policy_decision")
    return {"decision": decision} if decision else {}


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
