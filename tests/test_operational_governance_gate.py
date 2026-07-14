from aca_os.operational_governance_gate import assess_operational_governance


def _mapped(operation: str, *, category: str = "preparatory", outcome: str = "prepared"):
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


def test_governance_gate_allows_low_risk_preparation_without_tool_execution():
    assessment = assess_operational_governance(_mapped("prepare_claim_follow_up"))

    assert assessment["contract"] == "operational_governance_assessment.v1"
    assert assessment["mode"] == "shadow"
    assert assessment["executes_tools"] is False
    assert assessment["mutates_state"] is False
    assert assessment["changes_response"] is False
    assert assessment["risk"]["level"] == 1
    assert assessment["execution_allowed"] is True
    assert assessment["requires_confirmation"] is False


def test_governance_gate_blocks_external_write_without_tool_contract():
    assessment = assess_operational_governance(
        _mapped("open_ticket", category="coordinative"),
        governance_context={
            "available_evidence": ["issue_summary"],
            "permissions": {"execute:open_ticket": True},
            "user_confirmation": True,
        },
    )

    missing = {item["type"] for item in assessment["missing_preconditions"]}
    assert assessment["risk"]["level"] == 3
    assert assessment["execution_allowed"] is False
    assert "tool_unavailable" in missing
    assert "idempotency_unknown" in missing


def test_governance_gate_requires_confirmation_permission_and_idempotency_for_external_work():
    assessment = assess_operational_governance(
        _mapped("open_ticket", category="coordinative"),
        tool_contracts={
            "ticket_create": {
                "deterministic": False,
                "has_side_effects": True,
                "supports_dry_run": True,
                "supports_replay": True,
                "supports_shadow": False,
                "idempotency": "idempotent",
                "guarantee": "stable ticket id",
            }
        },
        governance_context={
            "available_evidence": ["issue_summary"],
            "permissions": {"execute:open_ticket": True},
            "user_confirmation": True,
        },
    )

    assert assessment["execution_allowed"] is True
    assert assessment["requires_confirmation"] is True
    assert assessment["permissions"]["allowed"] is True
    assert assessment["idempotency"]["safe"] is True


def test_governance_gate_keeps_high_liability_operation_manual_only():
    assessment = assess_operational_governance(
        _mapped("apply_service_credit", category="resolutive", outcome="completed"),
        tool_contracts={
            "billing_credit_apply": {
                "deterministic": False,
                "has_side_effects": True,
                "supports_dry_run": True,
                "supports_replay": True,
                "supports_shadow": False,
                "idempotency": "idempotent",
                "guarantee": "credit adjustment id",
            }
        },
        governance_context={
            "available_evidence": ["account_reference", "credit_reason"],
            "permissions": {"execute:apply_service_credit": True},
            "user_confirmation": True,
            "human_approval": True,
        },
    )

    missing = {item["type"] for item in assessment["missing_preconditions"]}
    assert assessment["risk"]["level"] == 4
    assert assessment["requires_human_approval"] is True
    assert assessment["manual_only"] is True
    assert assessment["execution_allowed"] is False
    assert "manual_only" in missing
