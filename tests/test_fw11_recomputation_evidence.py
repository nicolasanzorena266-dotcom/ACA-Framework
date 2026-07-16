from aca_kernel.core.events import Event
from aca_os.conversation_manager import ConversationManager
from aca_os.conversation_state import ConversationState
from aca_os.execution_trace import ExecutionTrace
from aca_os.fw11_recomputation_evidence import (
    build_turn_recomputation_evidence,
    classify_origin,
    diff_artifact,
)
from sdk.factory import build_galicia_runtime


def test_diff_artifact_reports_identical_when_writes_match():
    first = {"a": 1, "b": {"c": 2}}
    second = {"a": 1, "b": {"c": 2}}
    evidence = diff_artifact("conversation_plan", first, second)
    assert evidence["identical"] is True
    assert evidence["field_diff_count"] == 0
    assert evidence["field_diffs"] == []
    assert evidence["directly_consumed_by_narrative_response_composer"] is True


def test_diff_artifact_reports_field_level_differences():
    first = {"a": 1, "b": {"c": 2, "d": 3}}
    second = {"a": 1, "b": {"c": 5, "d": 3}}
    evidence = diff_artifact("conversation_intent_model", first, second)
    assert evidence["identical"] is False
    assert evidence["field_diff_count"] == 1
    assert evidence["field_diffs"] == [
        {"path": "b.c", "first_value": 2, "second_value": 5}
    ]


def test_diff_artifact_information_gain_plan_not_directly_consumed_by_composer():
    evidence = diff_artifact("information_gain_plan", {}, {"x": 1})
    assert evidence["directly_consumed_by_narrative_response_composer"] is False


def test_classify_origin_reports_no_change_when_state_is_identical():
    origin = classify_origin([])
    assert origin["input_state_changed"] is False
    assert origin["input_state_changed_fields"] == []


def test_classify_origin_reports_changed_fields():
    origin = classify_origin(
        [
            {
                "field": "active_mission",
                "category": "central",
                "component": "mission_manager",
                "before": None,
                "after": {},
            }
        ]
    )
    assert origin["input_state_changed"] is True
    assert origin["input_state_changed_fields"] == ["active_mission"]


def test_build_turn_recomputation_evidence_explains_difference_by_state_change():
    state_before = ConversationState(conversation_id="fw11-pure")
    state_after = ConversationState(
        conversation_id="fw11-pure", active_mission={"goal": "x"}
    )
    evidence = build_turn_recomputation_evidence(
        first_artifacts={
            "conversation_intent_model": {"a": 1},
            "information_gain_plan": {"a": 1},
            "conversation_plan": {"a": 1},
            "conversation_response_plan": {"a": 1},
        },
        second_artifacts={
            "conversation_intent_model": {"a": 2},
            "information_gain_plan": {"a": 1},
            "conversation_plan": {"a": 1},
            "conversation_response_plan": {"a": 1},
        },
        state_before_first=state_before,
        state_before_second=state_after,
    )
    assert evidence["contract"] == "fw11_recomputation_evidence.v1"
    assert evidence["package_id"] == "FW-11"
    assert evidence["authority_mode"] == "observation_only"
    assert evidence["decision_influence"] is False
    assert evidence["state_mutation"] is False
    assert evidence["recomputed_and_identical_artifacts"] == [
        "information_gain_plan",
        "conversation_plan",
        "conversation_response_plan",
    ]
    assert evidence["recomputed_and_differing_artifacts"] == [
        "conversation_intent_model"
    ]
    assert "active_mission" in evidence["origin"]["input_state_changed_fields"]
    assert evidence["unexplained_variance_artifacts"] == []
    assert evidence["observable_impact_artifacts"] == ["conversation_intent_model"]


def test_build_turn_recomputation_evidence_flags_unexplained_variance():
    state = ConversationState(conversation_id="fw11-unexplained")
    evidence = build_turn_recomputation_evidence(
        first_artifacts={"conversation_plan": {"a": 1}},
        second_artifacts={"conversation_plan": {"a": 2}},
        state_before_first=state,
        state_before_second=state,
    )
    assert evidence["origin"]["input_state_changed"] is False
    assert "conversation_plan" in evidence["unexplained_variance_artifacts"]
    assert "conversation_plan" in evidence["observable_impact_artifacts"]


def _event(message: str, conversation_id: str) -> Event:
    return Event(
        type="user_message",
        payload=message,
        metadata={"conversation_id": conversation_id},
    )


def _run(message: str, *, conversation_id: str):
    runtime = build_galicia_runtime()
    return runtime.process(_event(message, conversation_id))


def test_begin_turn_no_longer_computes_planning_artifacts_prematurely():
    """FW-11 resolution: the premature, pre-Mission write is gone.

    ConversationManager.begin_turn no longer computes ConversationIntentModel,
    InformationGainPlan, ConversationPlan or ConversationResponsePlan --
    MissionManager has not even run yet at that point, so this instrumentation
    proved nothing consumed that early value. The single remaining
    computation now happens in ACAOSRuntime.process, after MissionManager.
    """
    manager = ConversationManager()
    turn = manager.begin_turn(_event("Me chocaron ayer.", "fw11-single-writer"))
    derived = turn.conversation_state.derived_state
    assert "conversation_intent_model" not in derived
    assert "conversation_information_gain_plan" not in derived
    assert "conversation_plan" not in derived
    assert "conversation_response_plan" not in derived


def test_runtime_still_produces_the_single_authoritative_write():
    """The post-Mission write remains, unchanged, as the only writer."""
    state = _run("Me chocaron ayer.", conversation_id="fw11-single-writer-runtime")
    runtime_record = state.facts.get("conversation_state_runtime", {})

    # The instrumentation used to diagnose FW-11 is no longer wired into
    # production: there is nothing left to diff.
    assert "fw11_recomputation_evidence" not in runtime_record

    # The same audit-trail entries begin_turn used to record are still
    # produced, now sourced from the single authoritative computation.
    reasons = {projection.get("reason") for projection in runtime_record.get("projections", [])}
    assert "conversational_intent_decomposition" in reasons
    assert "information_gain_planning" in reasons
    assert "dynamic_conversation_planning" in reasons
    assert "conversation_response_planning" in reasons

    # The artifacts still reach the composer with real, mission-aware data
    # (active_plan.current_step populated), exactly as the second write
    # always produced before this change.
    plan = state.facts.get("conversation_plan", {}).get("plan", {})
    assert plan.get("active_plan", {}).get("current_step") is not None
    assert runtime_record.get("conversation_plan") == state.facts.get("conversation_plan")


def test_execution_trace_no_longer_carries_removed_instrumentation():
    state = _run("Que es la franquicia?", conversation_id="fw11-trace-removed")
    trace = ExecutionTrace.from_state(state)
    assert not hasattr(trace, "fw11_recomputation_evidence")
    assert "fw11_recomputation_evidence" not in trace.to_dict()
    assert "FW11_DUPLICATE_WRITER_EVIDENCE" not in trace.operations()
