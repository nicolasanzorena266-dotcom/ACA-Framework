from copy import deepcopy

from aca_kernel.core.events import Event
from aca_os.operational_work_mapper import map_operational_work
from sdk.factory import build_galicia_runtime


def _run(message: str, *, conversation_id: str = "operational-mapper-test"):
    runtime = build_galicia_runtime()
    return runtime.process(
        Event(
            type="user_message",
            payload=message,
            metadata={"conversation_id": conversation_id},
        )
    )


def test_operational_work_mapper_is_passive_and_does_not_change_response():
    state = _run(
        "Cargue una denuncia desde la app hace una semana y nadie me contacto.",
        conversation_id="operational-passive",
    )
    snapshot = state.to_dict()
    before = deepcopy(snapshot)

    mapped = map_operational_work(snapshot)

    assert snapshot == before
    assert state.response == before["response"]
    assert mapped["mode"] == "shadow"
    assert mapped["passive"] is True
    assert mapped["mutates_state"] is False
    assert mapped["changes_response"] is False


def test_operational_work_mapper_identifies_claim_follow_up_work():
    state = _run(
        "Cargue la denuncia hace una semana y nadie me contacto.",
        conversation_id="operational-claim-follow-up",
    )

    mapped = map_operational_work(state.to_dict())

    assert mapped["selected_work"]["operation"] == "prepare_claim_follow_up"
    assert mapped["selected_work"]["category"] == "preparatory"
    assert mapped["expected_outcome"] == "prepared"
    assert mapped["observed_inputs"]["conversation_response_plan"] is True
    assert mapped["observed_inputs"]["execution_plan"] is True


def test_operational_work_mapper_respects_blocked_capabilities():
    plugin_manifest = {
        "plugin": {"id": "galicia.insurance"},
        "handles": ["insurance.claims"],
        "blocked_capabilities": ["insurance.claim_status.lookup"],
        "public_actions": [
            {
                "id": "real_claim_status_lookup",
                "capability": "insurance.claim_status.lookup",
                "enabled": False,
                "disabled_reason": "No real lookup tool connected.",
            }
        ],
    }
    state = _run("Consulta mi expediente.", conversation_id="operational-blocked")

    mapped = map_operational_work(
        state.to_dict(),
        plugin_manifests=[plugin_manifest],
    )

    assert mapped["selected_work"]["operation"] == "block_real_status_lookup"
    assert mapped["expected_outcome"] == "blocked"
    assert mapped["blocked_by"][0]["type"] in {"public_action_disabled", "blocked_capability"}
    assert mapped["impossible_work_suggested"] is False


def test_operational_work_mapper_keeps_conversation_repair_as_work_projection():
    runtime = build_galicia_runtime()
    cid = "operational-repair"
    runtime.process(Event(type="user_message", payload="Me chocaron ayer.", metadata={"conversation_id": cid}))
    runtime.process(Event(type="user_message", payload="No hubo lesionados.", metadata={"conversation_id": cid}))
    state = runtime.process(Event(type="user_message", payload="Ya te lo dije.", metadata={"conversation_id": cid}))

    mapped = map_operational_work(state.to_dict())

    assert mapped["selected_work"]["operation"] == "repair_service_interaction"
    assert mapped["selected_work"]["category"] == "preparatory"
    assert mapped["expected_outcome"] == "prepared"


def test_operational_work_mapper_exposes_ordered_candidate_work_for_mixed_needs():
    state = _run(
        "No tengo internet y ademas la factura vino mal.",
        conversation_id="operational-mixed-candidates",
    )

    mapped = map_operational_work(state.to_dict())
    candidates = mapped["candidate_work"]
    operations = [candidate["operation"] for candidate in candidates]

    assert mapped["selected_work"]["operation"] == "continue_conversation_plan"
    assert operations[:3] == [
        "continue_conversation_plan",
        "diagnose_connectivity_issue",
        "prepare_billing_review",
    ]
    assert candidates[0]["work_role"] == "primary"
    assert candidates[1]["work_role"] == "secondary"
    assert candidates[2]["work_role"] == "secondary"
    assert mapped["candidate_summary"]["candidate_count"] >= 3


def test_operational_work_mapper_preserves_suspended_candidate_status():
    state = _run(
        "Dejemos la factura, ahora necesito arreglar el auto.",
        conversation_id="operational-suspended-candidate",
    )

    mapped = map_operational_work(state.to_dict())
    suspended = [
        candidate
        for candidate in mapped["candidate_work"]
        if candidate["operation"] == "prepare_billing_review"
    ]

    assert mapped["selected_work"]["operation"] == "provide_repair_risk_guidance"
    assert suspended
    assert suspended[0]["status"] == "suspended"
    assert suspended[0]["work_role"] == "suspended"
    assert suspended[0]["suspension_reason"] == "user_explicitly_deferred_this_work"


def test_operational_work_mapper_projects_case_state_without_reordering_candidates():
    state = _run(
        "Listo, la denuncia ya quedo cargada, pero no se si faltan documentos.",
        conversation_id="operational-case-state-projection",
    )

    mapped = map_operational_work(state.to_dict())
    original_order = [candidate["operation"] for candidate in mapped["candidate_work"]]
    projected_order = mapped["case_state_projected_ranking"]["projected_order"]

    assert original_order[:2] == ["prepare_claim_follow_up", "prepare_documentation_review"]
    assert projected_order[:2] == ["prepare_documentation_review", "prepare_claim_follow_up"]
    assert mapped["case_state_projected_ranking"]["changes_candidate_work"] is False
    assert mapped["case_state_projection"]["case_stage"] == "documentation_pending_after_claim_loaded"
    assert mapped["case_state_projection"]["claim"]["loaded"] is True
    assert mapped["case_state_projection"]["documentation"]["state"] in {"unknown_or_pending", "blocked_upload"}
    assert mapped["case_state_projection"]["persistent"] is False
    assert mapped["case_state_projection"]["reconstructable_each_turn"] is True
