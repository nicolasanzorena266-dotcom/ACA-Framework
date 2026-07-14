from aca_os.operational_audit_ledger import project_operational_audit_ledger
from aca_os.operational_governance_gate import assess_operational_governance


def _mapped(operation: str, *, category: str = "coordinative", outcome: str = "prepared"):
    return {
        "selected_work": {
            "operation": operation,
            "category": category,
            "expected_outcome": outcome,
            "confidence": 0.95,
        },
        "candidate_work": [
            {
                "operation": operation,
                "category": category,
                "expected_outcome": outcome,
                "evidence": {"source": "test"},
                "blocked_by": [],
            }
        ],
        "case_state_projection": {},
        "blocked_by": [],
    }


def _ticket_contract():
    return {
        "ticket_create": {
            "deterministic": False,
            "has_side_effects": True,
            "supports_dry_run": True,
            "supports_replay": True,
            "supports_shadow": False,
            "idempotency": "idempotent",
            "guarantee": "stable ticket id",
        }
    }


def test_operational_audit_ledger_is_shadow_and_complete_for_allowed_external_work():
    mapped = _mapped("open_ticket")
    governance = assess_operational_governance(
        mapped,
        tool_contracts=_ticket_contract(),
        governance_context={
            "available_evidence": ["issue_summary"],
            "permissions": {"execute:open_ticket": True},
            "user_confirmation": True,
        },
    )

    ledger = project_operational_audit_ledger(
        mapped,
        governance,
        tool_contracts=_ticket_contract(),
        ledger_context={
            "conversation_id": "ledger-test",
            "timestamp": "2026-07-13T10:00:00+00:00",
            "user_confirmation": True,
        },
    )

    assert ledger["contract"] == "operational_audit_ledger_record.v1"
    assert ledger["mode"] == "shadow"
    assert ledger["persistent"] is False
    assert ledger["executes_tools"] is False
    assert ledger["completeness"]["complete"] is True
    assert ledger["execution_status"]["state"] == "would_execute"
    assert ledger["projected_request"]["payload_projection"]["contains_raw_payload"] is False


def test_operational_audit_ledger_detects_duplicate_idempotency_key():
    mapped = _mapped("schedule_technical_visit")
    contracts = {
        "technical_visit_scheduler": {
            "deterministic": False,
            "has_side_effects": True,
            "supports_dry_run": True,
            "supports_replay": True,
            "supports_shadow": False,
            "idempotency": "requires_idempotency_key",
            "guarantee": "Provider accepts idempotency key.",
        }
    }
    context = {
        "available_evidence": ["technical_diagnosis", "service_address"],
        "permissions": {"execute:schedule_technical_visit": True},
        "user_confirmation": True,
        "idempotency_key": "visit-001",
    }
    governance = assess_operational_governance(mapped, tool_contracts=contracts, governance_context=context)

    ledger = project_operational_audit_ledger(
        mapped,
        governance,
        tool_contracts=contracts,
        ledger_context={
            **context,
            "conversation_id": "ledger-duplicate",
            "timestamp": "2026-07-13T10:00:00+00:00",
            "previous_ledger_records": [
                {
                    "ledger_id": "prior",
                    "selected_work": {"operation": "schedule_technical_visit"},
                    "tool": {"name": "technical_visit_scheduler"},
                    "idempotency": {"key": "visit-001"},
                }
            ],
        },
    )

    assert ledger["duplicate_detection"]["duplicate_detected"] is True
    assert ledger["execution_status"]["state"] == "duplicate_detected_shadow"


def test_operational_audit_ledger_marks_retry_unsafe_without_idempotency_key():
    mapped = _mapped("schedule_technical_visit")
    contracts = {
        "technical_visit_scheduler": {
            "deterministic": False,
            "has_side_effects": True,
            "supports_dry_run": True,
            "supports_replay": True,
            "supports_shadow": False,
            "idempotency": "requires_idempotency_key",
            "guarantee": "Provider accepts idempotency key.",
        }
    }
    governance = assess_operational_governance(
        mapped,
        tool_contracts=contracts,
        governance_context={
            "available_evidence": ["technical_diagnosis", "service_address"],
            "permissions": {"execute:schedule_technical_visit": True},
            "user_confirmation": True,
        },
    )

    ledger = project_operational_audit_ledger(
        mapped,
        governance,
        tool_contracts=contracts,
        ledger_context={
            "conversation_id": "ledger-retry",
            "timestamp": "2026-07-13T10:00:00+00:00",
            "user_confirmation": True,
        },
    )

    assert ledger["idempotency"]["covered"] is False
    assert ledger["replay_safety"]["safe"] is False
    assert ledger["execution_status"]["state"] == "blocked_by_governance"


def test_operational_audit_ledger_keeps_irreversible_action_manual():
    mapped = _mapped("cancel_service", category="resolutive", outcome="completed")
    contracts = {
        "service_cancel": {
            "deterministic": False,
            "has_side_effects": True,
            "supports_dry_run": True,
            "supports_replay": False,
            "supports_shadow": False,
            "idempotency": "requires_idempotency_key",
            "guarantee": "Cancellation API accepts idempotency key.",
        }
    }
    context = {
        "available_evidence": ["verified_identity", "cancellation_confirmation"],
        "permissions": {"execute:cancel_service": True},
        "user_confirmation": True,
        "human_approval": True,
        "idempotency_key": "cancel-001",
    }
    governance = assess_operational_governance(mapped, tool_contracts=contracts, governance_context=context)
    ledger = project_operational_audit_ledger(
        mapped,
        governance,
        tool_contracts=contracts,
        ledger_context={
            **context,
            "conversation_id": "ledger-manual",
            "timestamp": "2026-07-13T10:00:00+00:00",
        },
    )

    assert ledger["execution_status"]["state"] == "manual_only"
    assert ledger["compensation_strategy"]["status"] == "manual_control_required"
    assert ledger["approval_status"]["status"] == "approved"
