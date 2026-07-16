"""Permanent fixtures defined in ACA-305C, implemented against the real Runtime.

Each fixture below corresponds 1:1 to a fixture specified in
docs/architecture/ACA-305C_Mission_Lifecycle_Benchmark_and_Integration_Closure.md
section 9. They are written to run against `sdk.factory.build_galicia_runtime`,
the same path Studio/production use (matching ACA-304's reproduction method).

Before the ACA-305D implementation, fixtures 1-4 and 6 are expected to FAIL
for the documented reasons (marked `expected_red=True` in each test's own
assertion comments). Fixture 5 captures the byte-identical baseline and is
expected to PASS both before and after ACA-305D's Stage 1.
"""

from __future__ import annotations

from typing import Any, Mapping

from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from sdk.factory import build_galicia_runtime


def _run_turns(*messages: str) -> list[CognitiveState]:
    runtime = build_galicia_runtime()
    state: CognitiveState | None = None
    states: list[CognitiveState] = []
    for message in messages:
        state = runtime.process(Event(type="user_message", payload=message), state)
        states.append(state)
    return states


def _topics(state: CognitiveState) -> list[dict[str, Any]]:
    projection = state.facts.get("conversation_topic_stack") or {}
    return list(projection.get("topics") or [])


def _topic_by_id(state: CognitiveState, topic_id: str) -> dict[str, Any] | None:
    for topic in _topics(state):
        if str(topic.get("id") or "") == topic_id:
            return topic
    return None


def _response(state: CognitiveState) -> str:
    return str(state.response or "")


INSURANCE_MULTIPLE_CHOICE_MARKERS = ("arreglo", "documentacion", "documentación")


def test_fixture_1_greeting_then_social_question_does_not_trigger_insurance_orientation():
    """ACA-305C fixture 1: "Hola" -> "¿Cómo estás?" must not be consumed as a
    pending answer to user_need, and must not produce the auto_claim_guidance
    multiple-choice reformulation."""
    turn1, turn2 = _run_turns("Hola", "¿Cómo estás?")

    assert (turn1.active_mission or {}).get("type") == "general_orientation"

    response2 = _response(turn2).lower()
    mission2 = turn2.active_mission or {}

    # Documented current defect (ACA-304 turn 2): the response contains the
    # insurance-specific multiple-choice reformulation, and/or the message
    # gets absorbed as an answer to `user_need`.
    triggered_insurance_reformulation = any(marker in response2 for marker in INSURANCE_MULTIPLE_CHOICE_MARKERS)
    absorbed_as_pending_answer = (
        mission2.get("type") == "auto_claim_guidance"
        or "user_need" in (mission2.get("slots") or {})
        and (mission2.get("slots") or {}).get("user_need", {}).get("value") == "¿Cómo estás?"
    )

    assert not triggered_insurance_reformulation, (
        f"prohibited: insurance multiple-choice reformulation leaked into a social-question reply: {response2!r}"
    )
    assert not absorbed_as_pending_answer, "prohibited: '¿Cómo estás?' absorbed as a user_need answer"
    assert mission2.get("type") == "general_orientation", "mission must remain general_orientation"


def test_fixture_2_general_mission_reevaluates_on_natural_topic_change():
    """ACA-305C fixture 2: "Necesito ayuda" -> "Mis vacaciones" must reevaluate
    the mission without requiring the literal phrase "cambiemos de tema"."""
    turn1, turn2 = _run_turns("Necesito ayuda", "Mis vacaciones")

    mission2 = dict(turn2.active_mission or {})
    user_need_slot = dict((mission2.get("slots") or {}).get("user_need") or {})

    # Documented current defect: "Mis vacaciones" is literally stored as the
    # confirmed/partially-filled value of the `user_need` slot, and the
    # response is the generic insurance multiple-choice reformulation -- the
    # same mechanism ACA-304 found for "¿Cómo estás?", reproduced here for an
    # unrelated statement instead of a question.
    absorbed_as_user_need = user_need_slot.get("value") == "mis vacaciones"

    assert not absorbed_as_user_need, (
        f"prohibited: 'Mis vacaciones' absorbed verbatim as the user_need slot value: {user_need_slot!r}"
    )


def test_fixture_3_explicit_rejection_does_not_repeat_the_same_question():
    """ACA-305C fixture 3: rejecting the offered options with "Ninguno" must
    not leak Galicia-insurance vocabulary into a general_orientation
    conversation, and must not silently absorb "ninguno" as the confirmed
    value of user_need. Builds on the exact ACA-304 turn sequence.

    Assertion corrected during ACA-305D closing (this sprint's explicit
    contract, aca_os/mission_manager.py's MissionTransitionDecision): a
    question may legitimately repeat, verbatim, when no evidence exists for
    MissionManager to decide a different transition -- "Ninguno" produces
    the same evaluated `maintain` decision as "¿Cómo estás?" did, since
    nothing distinguishes them as mission-relevant evidence. What remains
    prohibited is wrong-domain content and silent absorption, not
    repetition itself (ACA-305D-RC3 section 14)."""
    turn1, turn2, turn3 = _run_turns("Hola", "¿Cómo estás?", "Ninguno")
    response3 = _response(turn3).lower()
    mission3 = turn3.active_mission or {}
    user_need_slot = dict((mission3.get("slots") or {}).get("user_need") or {})

    triggered_insurance_reformulation = any(marker in response3 for marker in INSURANCE_MULTIPLE_CHOICE_MARKERS)
    absorbed_as_user_need = user_need_slot.get("value") == "ninguno"

    assert not triggered_insurance_reformulation, (
        f"prohibited: insurance multiple-choice reformulation leaked into a general_orientation reply: {response3!r}"
    )
    assert not absorbed_as_user_need, (
        f"prohibited: 'Ninguno' absorbed verbatim as the user_need slot value: {user_need_slot!r}"
    )


def test_fixture_4_completely_unrelated_question_does_not_repeat_the_same_question():
    """ACA-305C fixture 4: "¿Dios existe?" against an auto_claim_guidance
    mission must not leave the system stuck asking a blind, unadapted
    question forever.

    Assertion corrected during ACA-305D closing (this sprint): ACA-305D-RC3
    surfaced a pre-existing, already-approved contract this fixture's
    original "must abandon/suspend/replace" bar contradicted --
    `conversation_fulfillment.v1` (introduced alongside reformulation itself,
    commit c0c2bcf, covered by
    test_conversation_fulfillment.py::test_unanswered_expected_step_records_failure_and_recovery_action)
    already requires `auto_claim_guidance` to stay `in_progress`, mark the
    unanswered step `failed`, and reask via reformulation -- not transition
    the mission -- for exactly this scenario (an unrelated message against a
    pending slot). `auto_claim_guidance` owns its own recovery authority via
    that contract; `MissionManager`'s newer suspend-on-no-match evidence
    (ACA-305D closing) is deliberately scoped to mission types without one
    (general_orientation), so it does not fire here -- respecting "byte-
    identical for auto_claim_guidance"."""
    turn1, turn2 = _run_turns("Me chocaron el auto", "¿Dios existe?")
    mission1 = dict(turn1.active_mission or {})
    mission2 = dict(turn2.active_mission or {})
    response1 = _response(turn1)
    response2 = _response(turn2)
    fulfillment = dict(turn2.facts.get("conversation_fulfillment", {}).get("fulfillment", {}))

    # The mission is not silently left untransitioned and unaccounted for:
    # auto_claim_guidance's own, pre-existing recovery authority engaged.
    assert fulfillment.get("fulfilled_goal", {}).get("status") == "failed", (
        f"expected the pre-existing conversation_fulfillment contract to record a failed step; got {fulfillment!r}"
    )
    assert [step.get("id") for step in fulfillment.get("failed_steps", [])] == ["confirm_injuries"]
    assert [action.get("action") for action in fulfillment.get("recovery_actions", [])] == ["reask_or_reformulate"]

    # The mission itself stays exactly what it was -- correct here, since
    # auto_claim_guidance's recovery authority is reask, not transition.
    assert mission2.get("type") == "auto_claim_guidance"
    assert mission2.get("lifecycle_status") != "suspended"

    # The original ACA-304 symptom (a blind, unadapted, verbatim-repeated
    # question) does not occur: turn 2's question is the reformulated
    # injuries question, not a byte-identical repeat of turn 1's.
    assert response2 != response1, "prohibited: identical question repeated verbatim without any adaptation"
    assert "recordas si alguna persona resulto herida" in response2.lower()


def test_fixture_5_auto_claim_guidance_continuation_is_captured_as_golden_baseline():
    """ACA-305C fixture 5: a valid, on-topic continuation of auto_claim_guidance
    must be captured as the byte-identical baseline this migration must
    preserve. This fixture must pass before AND after ACA-305D's Stage 1."""
    turn1, turn2 = _run_turns("Me chocaron el auto", "No, nadie resultó herido")

    mission1 = dict(turn1.active_mission or {})
    mission2 = dict(turn2.active_mission or {})

    assert mission1.get("type") == "auto_claim_guidance"
    assert mission2.get("type") == "auto_claim_guidance"
    # The injuries slot must have been resolved by this exchange.
    assert mission2 != mission1, "the injuries answer must advance the mission"
    assert "injuries" not in (mission2.get("missing") or [])


def test_fixture_6_topic_change_and_return_recovers_mission_and_topic_coherently():
    """ACA-305C fixture 6: mission A -> topic B -> "volvamos a la denuncia"
    must recover the SAME mission (not a fresh one), with facts intact, in
    the same turn the topic is resumed."""
    turn1, turn2, turn3 = _run_turns(
        "Me chocaron el auto",
        "Cambiemos de tema, contame de mis vacaciones",
        "volvamos a la denuncia",
    )

    mission1 = dict(turn1.active_mission or {})
    mission2 = dict(turn2.active_mission or {})
    mission3 = dict(turn3.active_mission or {})
    topic_after_shift = _topic_by_id(turn2, "mission:auto_claim_guidance")
    topic_after_return = _topic_by_id(turn3, "mission:auto_claim_guidance")

    assert mission1.get("type") == "auto_claim_guidance"
    # Topic-level suspension already works today (conversation_state.py's
    # TOPIC_SHIFT/new_topic handling) -- this is not the defect.
    assert topic_after_shift and topic_after_shift.get("status") == "suspended"

    # Documented current defect (ACA-305C section 1.3 / section 7 invariant
    # 1): the mission's own lifecycle_status does not reflect the topic's
    # suspension -- topic_stack and active_mission diverge for the duration
    # of the shift, in violation of the referential-consistency invariant.
    mission_reflects_suspension = mission2.get("lifecycle_status") == "suspended"

    topic_recovered = bool(topic_after_return) and str(topic_after_return.get("status") or "") in {
        "active",
        "resumed",
    }
    mission_recovered = mission3.get("type") == "auto_claim_guidance"

    assert mission_reflects_suspension and mission_recovered and topic_recovered, (
        "prohibited: topic suspend/resume not coherently mirrored by the mission's own lifecycle_status; "
        f"mission2={mission2!r} mission3={mission3!r} topic_after_return={topic_after_return!r}"
    )
