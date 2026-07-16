"""FW-11 duplicate-writer diagnostic tool (historical; not wired into production).

FW-11 has been resolved. ConversationIntentModel, InformationGainPlan,
ConversationPlan and ConversationResponsePlan used to be computed twice per
turn: once in ConversationManager.begin_turn (before MissionManager assigned
the active mission) and again in ACAOSRuntime.process (after
MissionManager.before_kernel runs), with the second write silently
overwriting the first. Evidence gathered with this module (diffed across
real turns) showed that:

    * nothing between the two writes ever consumed the first write's
      output (verified by grepping every consumer of these four artifacts:
      MissionManager, PolicyManager, the zero_cost intent/action/flow layer,
      and the runtime's own intent-adjustment helpers do not read them);
    * the second write always reached NarrativeResponseComposer, exactly as
      the original design intended;
    * every observed difference between the two writes was fully explained
      by MissionManager assigning the active mission in between them (no
      unexplained/nondeterministic variance was ever observed).

Given that, the premature first write was removed (see aca_os/runtime.py and
aca_os/conversation_manager.py); the second write, after MissionManager, is
now the single authoritative computation. This module is kept only as a
standalone, manually-invokable diagnostic tool -- the diffing/origin/impact
utilities below are generic and can be reused for future migrations that
need the same kind of "does removing this duplicate write change anything"
evidence (see aca_os/semantic_firewall_plan.py for other duplicate-writer
candidates, e.g. intent_match under package FW-12). It is not imported by
aca_os/runtime.py or aca_os/conversation_manager.py.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Sequence

from aca_os.conversation_state import ConversationState, conversation_state_diff

PACKAGE_ID = "FW-11"

_ARTIFACT_ORDER = (
    "conversation_intent_model",
    "information_gain_plan",
    "conversation_plan",
    "conversation_response_plan",
)

# NarrativeResponseComposer.compose() reads these three artifacts directly
# from CognitiveState.facts via _trace_payload(state, <key>, ...). It never
# reads information_gain_plan directly -- that artifact only reaches the
# composer indirectly, embedded inside conversation_plan/response_plan.
_DIRECTLY_CONSUMED_BY_COMPOSER = frozenset(
    {"conversation_response_plan", "conversation_plan", "conversation_intent_model"}
)

_MAX_FIELD_DIFFS = 20


def _diff_leaves(before: Any, after: Any, path: str = "") -> List[Dict[str, Any]]:
    """Recursive, dict-aware leaf diff.

    Nested mappings are compared field by field. Lists and scalars are
    compared as whole values (no per-index list diffing), which keeps this
    evidence-only utility simple and bounded.
    """
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        diffs: List[Dict[str, Any]] = []
        for key in sorted(set(before) | set(after)):
            child_path = f"{path}.{key}" if path else str(key)
            diffs.extend(_diff_leaves(before.get(key), after.get(key), child_path))
        return diffs
    if before == after:
        return []
    return [{"path": path or "<root>", "first_value": deepcopy(before), "second_value": deepcopy(after)}]


def diff_artifact(
    artifact: str,
    first: Mapping[str, Any] | None,
    second: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    """Field-level diff between the first and second write of one artifact."""
    first_dict = dict(first or {})
    second_dict = dict(second or {})
    all_diffs = _diff_leaves(first_dict, second_dict)
    return {
        "artifact": artifact,
        "package_id": PACKAGE_ID,
        "first_present": bool(first_dict),
        "second_present": bool(second_dict),
        "identical": not all_diffs,
        "field_diff_count": len(all_diffs),
        "field_diffs": all_diffs[:_MAX_FIELD_DIFFS],
        "truncated": len(all_diffs) > _MAX_FIELD_DIFFS,
        "directly_consumed_by_narrative_response_composer": artifact in _DIRECTLY_CONSUMED_BY_COMPOSER,
    }


def classify_origin(input_state_diff: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Summarize what changed in ConversationState between the two writes.

    If ConversationState itself did not change between the first and second
    write, any artifact difference cannot be explained by new information
    arriving -- it is evidence that recomputation is not stable given the
    same input (unexplained variance), which is a stronger finding than a
    difference explained by e.g. MissionManager advancing the mission.
    """
    changed_fields = sorted(
        {str(item.get("field")) for item in input_state_diff if item.get("field")}
    )
    return {
        "input_state_changed": bool(changed_fields),
        "input_state_changed_fields": changed_fields,
        "input_state_diff": [dict(item) for item in input_state_diff],
    }


def build_turn_recomputation_evidence(
    *,
    first_artifacts: Mapping[str, Mapping[str, Any]],
    second_artifacts: Mapping[str, Mapping[str, Any]],
    state_before_first: ConversationState | None,
    state_before_second: ConversationState | None,
) -> Dict[str, Any]:
    """Build one turn's FW-11 duplicate-writer evidence record.

    Pure observation. Does not mutate ConversationState, does not select a
    winner between the two writes, and does not change runtime behavior.
    """
    input_state_mutations = (
        conversation_state_diff(state_before_first, state_before_second)
        if state_before_second is not None
        else []
    )
    input_state_diff = [mutation.to_dict() for mutation in input_state_mutations]
    origin = classify_origin(input_state_diff)

    artifacts: Dict[str, Any] = {}
    identical: List[str] = []
    differing: List[str] = []
    unexplained_variance: List[str] = []
    observable_impact: List[str] = []

    for artifact in _ARTIFACT_ORDER:
        evidence = diff_artifact(
            artifact,
            first_artifacts.get(artifact),
            second_artifacts.get(artifact),
        )
        artifacts[artifact] = evidence
        if evidence["identical"]:
            identical.append(artifact)
            continue
        differing.append(artifact)
        if not origin["input_state_changed"]:
            unexplained_variance.append(artifact)
        if evidence["directly_consumed_by_narrative_response_composer"]:
            observable_impact.append(artifact)

    return {
        "contract": "fw11_recomputation_evidence.v1",
        "component": "fw11_recomputation_evidence",
        "package_id": PACKAGE_ID,
        "authority_mode": "observation_only",
        "decision_influence": False,
        "state_mutation": False,
        "note": (
            "Both writes still occur exactly as before this instrumentation; "
            "this record only observes them. The second write remains the "
            "one that reaches NarrativeResponseComposer, unchanged from "
            "current behavior."
        ),
        "origin": origin,
        "artifacts": artifacts,
        "recomputed_and_identical_artifacts": identical,
        "recomputed_and_differing_artifacts": differing,
        "unexplained_variance_artifacts": unexplained_variance,
        "observable_impact_artifacts": observable_impact,
    }
