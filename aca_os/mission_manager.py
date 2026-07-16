from copy import deepcopy

from aca_core.text import normalize_text
from aca_kernel.core.events import Event
from aca_kernel.core.state import CognitiveState
from aca_os.conversation_state import MISSION_LIFECYCLE, ConversationState, MissionLifecycleStatus

MISSION_TRANSITION_DECISION_CONTRACT = "mission_transition_decision.v1"

TRANSITION_MAINTAIN = "maintain"
TRANSITION_COMPLETE = "complete"
TRANSITION_SUSPEND = "suspend"
TRANSITION_RESUME = "resume"
TRANSITION_REPLACE = "replace"
TRANSITION_ABANDON = "abandon"

VALID_TRANSITION_TYPES = {
    TRANSITION_MAINTAIN,
    TRANSITION_COMPLETE,
    TRANSITION_SUSPEND,
    TRANSITION_RESUME,
    TRANSITION_REPLACE,
    TRANSITION_ABANDON,
}

# ACA-305B section 9 step 3: fixed precedence order for resolving multiple
# proposals in the same turn.
TRANSITION_PRECEDENCE = {
    TRANSITION_ABANDON: 6,
    TRANSITION_REPLACE: 5,
    TRANSITION_COMPLETE: 4,
    TRANSITION_SUSPEND: 3,
    TRANSITION_RESUME: 2,
    TRANSITION_MAINTAIN: 1,
}

# ACA-305B section 7: starting confidence thresholds per transition type,
# explicitly flagged there as tuning inputs for a later benchmark pass, not
# final values.
MINIMUM_CONFIDENCE = {
    TRANSITION_MAINTAIN: 0.50,
    TRANSITION_RESUME: 0.65,
    TRANSITION_SUSPEND: 0.65,
    TRANSITION_COMPLETE: 0.75,
    TRANSITION_REPLACE: 0.85,
    TRANSITION_ABANDON: 0.85,
}

# ACA-305B section 3.2/3.3: explicit emitter allowlist. Only components that
# have already been evidenced to compute mission-relevant signals may
# propose. Output/response, routing, and shadow/non-authoritative components
# are never in this set.
ALLOWED_PROPOSAL_COMPONENTS = {"conversation_state"}

_COMPLETE_ELIGIBLE_STATUSES = {
    MissionLifecycleStatus.READY_TO_PROGRESS,
    MissionLifecycleStatus.PROGRESSING,
}
_SUSPEND_ELIGIBLE_STATUSES = {
    MissionLifecycleStatus.INITIALIZED,
    MissionLifecycleStatus.GATHERING_INFORMATION,
    MissionLifecycleStatus.READY_TO_PROGRESS,
    MissionLifecycleStatus.PROGRESSING,
    MissionLifecycleStatus.WAITING_USER,
    MissionLifecycleStatus.COMPLETED,
}
_RESUME_ELIGIBLE_STATUSES = {MissionLifecycleStatus.SUSPENDED}


class MissionManager:
    def before_kernel(
        self,
        event: Event,
        state: CognitiveState | None = None,
        *,
        conversation_state: ConversationState | None = None,
    ) -> CognitiveState:
        current = state or CognitiveState()
        if current.active_mission:
            proposals = (
                list(conversation_state.derived_state.get("mission_transition_proposals") or [])
                if conversation_state is not None
                else []
            )
            turn = int(conversation_state.turn_count) if conversation_state is not None else 0
            decision = evaluate_mission_transition_proposals(
                mission_before=current.active_mission,
                proposals=proposals,
                turn=turn,
            )
            facts = dict(current.facts)
            facts["mission_transition_decision"] = decision
            return current.evolve(
                "MISSION_TRANSITION",
                active_mission=decision["mission_after"],
                facts=facts,
            )
        if conversation_state is not None and conversation_state.active_mission:
            return current.evolve(
                "MISSION_LOAD_FROM_CONVERSATION_STATE",
                active_mission=dict(conversation_state.active_mission),
            )
        if _planned_flow(current) == "knowledge_lookup":
            action_plan = current.facts.get("zero_cost_action_plan", {})
            payload = action_plan.get("payload", {}) if isinstance(action_plan, dict) else {}
            concept_key = payload.get("tool_key") if isinstance(payload, dict) else None
            mission = {
                "type": "knowledge_lookup",
                "goal": "explicar un concepto usando evidencia estructurada",
                "status": "in_progress",
                "lifecycle_status": "initialized",
                "progress": 0.25,
                "next_act": "provide_concept_explanation",
                "blockers": [],
                "missing": [],
            }
            if concept_key:
                mission["concept_key"] = concept_key
            return current.evolve("MISSION_CREATE", active_mission=mission)

        text = normalize_text(event.payload)
        if _planned_flow(current) == "guided_process" or any(x in text for x in ["me chocaron", "choque", "chocaron", "accidente", "siniestro", "denuncia"]):
            mission = {
                "type": "auto_claim_guidance",
                "goal": "orientar correctamente al usuario sobre un siniestro automotor",
                "status": "in_progress",
                "lifecycle_status": "initialized",
                "progress": 0.10,
                "next_act": "ask_injuries",
                "blockers": ["injuries_unknown", "user_role_unknown"],
                "missing": ["injuries", "user_role"],
            }
        else:
            mission = {
                "type": "general_orientation",
                "goal": "comprender la necesidad del usuario y orientar sin inventar",
                "status": "in_progress",
                "lifecycle_status": "initialized",
                "progress": 0.05,
                "next_act": "ask_user_need",
                "blockers": ["need_more_context"],
                "missing": ["user_need"],
            }
        return current.evolve("MISSION_CREATE", active_mission=mission)

    def after_kernel(
        self,
        state: CognitiveState,
        *,
        conversation_state: ConversationState | None = None,
    ) -> CognitiveState:
        if not state.active_mission:
            return state
        mission = dict(state.active_mission)
        if state.response:
            mission["progress"] = max(float(mission.get("progress", 0)), 0.75)
        return state.evolve("MISSION_UPDATE", active_mission=mission)


def _planned_flow(state: CognitiveState) -> str | None:
    execution_plan = state.facts.get("zero_cost_execution_plan")
    if not isinstance(execution_plan, dict):
        return None
    flow = execution_plan.get("flow")
    return str(flow) if flow else None


def _validate_proposal(proposal: object, *, turn: int) -> list[str]:
    if not isinstance(proposal, dict):
        return ["malformed_proposal"]
    errors: list[str] = []
    for field in ("component", "transition_type", "mission_before", "mission_delta", "confidence", "turn"):
        if field not in proposal:
            return ["malformed_proposal"]
    if proposal.get("component") not in ALLOWED_PROPOSAL_COMPONENTS:
        errors.append("unauthorized_emitter")
    if proposal.get("transition_type") not in VALID_TRANSITION_TYPES:
        errors.append("unknown_transition_type")
    try:
        if int(proposal.get("turn")) != int(turn):
            errors.append("stale_evidence")
    except (TypeError, ValueError):
        errors.append("malformed_proposal")
    return errors


def _is_legal_transition(*, transition_type: str, current_status: str, target_status: str | None) -> bool:
    if transition_type == TRANSITION_MAINTAIN:
        if target_status is None or target_status == current_status:
            return True
        return target_status in MISSION_LIFECYCLE.get(current_status, ())
    if transition_type == TRANSITION_COMPLETE:
        return current_status in _COMPLETE_ELIGIBLE_STATUSES
    if transition_type == TRANSITION_SUSPEND:
        return current_status in _SUSPEND_ELIGIBLE_STATUSES
    if transition_type == TRANSITION_RESUME:
        return current_status in _RESUME_ELIGIBLE_STATUSES
    if transition_type in (TRANSITION_REPLACE, TRANSITION_ABANDON):
        return True
    return False


def _rejected_decision(
    *,
    turn: int,
    proposals_considered: list[dict],
    mission_before: dict | None,
    rejection_reason: str,
) -> dict:
    return {
        "contract": MISSION_TRANSITION_DECISION_CONTRACT,
        "turn": int(turn),
        "proposals_considered": proposals_considered,
        "winning_proposal_id": None,
        "transition_type": "maintain",
        "accepted": False,
        "rejection_reason": rejection_reason,
        "mission_before": deepcopy(mission_before),
        "mission_after": deepcopy(mission_before),
        "predecessor_mission": None,
        "topic_effect": None,
        "component": "mission_manager",
    }


def evaluate_mission_transition_proposals(
    *,
    mission_before: dict | None,
    proposals: list,
    turn: int,
) -> dict:
    """The sole evaluation/decision procedure for mission transitions
    (ACA-305B sections 4 and 9). Proposals are inert input; this function is
    the only place a `mission_after` is computed. Callers (MissionManager)
    are the only code allowed to write the result into CognitiveState.
    """

    proposals_considered: list[dict] = []
    seen_ids: set[str] = set()
    candidates: list[dict] = []

    for proposal in proposals or ():
        proposal_id = proposal.get("proposal_id") if isinstance(proposal, dict) else None
        if proposal_id and proposal_id in seen_ids:
            continue
        if proposal_id:
            seen_ids.add(proposal_id)
        errors = _validate_proposal(proposal, turn=turn)
        proposals_considered.append(
            {
                "proposal_id": proposal_id,
                "component": proposal.get("component") if isinstance(proposal, dict) else None,
                "transition_type": proposal.get("transition_type") if isinstance(proposal, dict) else None,
                "confidence": proposal.get("confidence") if isinstance(proposal, dict) else None,
                "valid": not errors,
                "validation_errors": errors,
            }
        )
        if not errors:
            candidates.append(proposal)

    if not candidates:
        return {
            "contract": MISSION_TRANSITION_DECISION_CONTRACT,
            "turn": int(turn),
            "proposals_considered": proposals_considered,
            "winning_proposal_id": None,
            "transition_type": "maintain",
            "accepted": True,
            "rejection_reason": "",
            "mission_before": deepcopy(mission_before),
            "mission_after": deepcopy(mission_before),
            "predecessor_mission": None,
            "topic_effect": None,
            "component": "mission_manager",
        }

    candidates.sort(key=lambda p: TRANSITION_PRECEDENCE.get(p.get("transition_type"), 0), reverse=True)
    winner = candidates[0]

    # Same-type `maintain` proposals with disjoint fields are merged
    # (ACA-305B section 9 step 3 / section 17 edge case 1). A field
    # disagreement between two `maintain` proposals is left unresolved
    # (rejected) rather than guessed at.
    if winner.get("transition_type") == TRANSITION_MAINTAIN:
        merged_delta = dict(winner.get("mission_delta") or {})
        conflict = False
        for other in candidates[1:]:
            if other.get("transition_type") != TRANSITION_MAINTAIN:
                break
            for key, value in (other.get("mission_delta") or {}).items():
                if key in merged_delta and merged_delta[key] != value:
                    conflict = True
                    break
                merged_delta[key] = value
            if conflict:
                break
        if conflict:
            return _rejected_decision(
                turn=turn,
                proposals_considered=proposals_considered,
                mission_before=mission_before,
                rejection_reason="unresolved_proposal_conflict",
            )
        winner = {**winner, "mission_delta": merged_delta}

    transition_type = winner.get("transition_type")
    current_status = str((mission_before or {}).get("lifecycle_status") or MissionLifecycleStatus.INITIALIZED)

    if current_status == MissionLifecycleStatus.COMPLETED and transition_type not in (TRANSITION_SUSPEND, TRANSITION_MAINTAIN):
        return _rejected_decision(
            turn=turn,
            proposals_considered=proposals_considered,
            mission_before=mission_before,
            rejection_reason="mission_already_terminal",
        )

    if transition_type == TRANSITION_REPLACE:
        target_type = winner.get("target_mission_type")
        if target_type and mission_before and target_type == mission_before.get("type"):
            return _rejected_decision(
                turn=turn,
                proposals_considered=proposals_considered,
                mission_before=mission_before,
                rejection_reason="replace_target_equals_current_type",
            )

    confidence = float(winner.get("confidence") or 0.0)
    minimum = MINIMUM_CONFIDENCE.get(transition_type, 1.0)
    if confidence < minimum:
        return _rejected_decision(
            turn=turn,
            proposals_considered=proposals_considered,
            mission_before=mission_before,
            rejection_reason="confidence_below_threshold",
        )

    target_status = (winner.get("mission_delta") or {}).get("lifecycle_status")
    if not _is_legal_transition(transition_type=transition_type, current_status=current_status, target_status=target_status):
        return _rejected_decision(
            turn=turn,
            proposals_considered=proposals_considered,
            mission_before=mission_before,
            rejection_reason="illegal_transition",
        )

    predecessor_mission = None
    if transition_type == TRANSITION_ABANDON:
        mission_after = None
        predecessor_mission = deepcopy(mission_before)
    elif transition_type == TRANSITION_REPLACE:
        mission_after = deepcopy(winner.get("mission_delta") or {})
        predecessor_mission = deepcopy(mission_before)
    else:
        proposal_mission_before = winner.get("mission_before") or mission_before
        mission_after = {**deepcopy(proposal_mission_before), **deepcopy(winner.get("mission_delta") or {})}

    return {
        "contract": MISSION_TRANSITION_DECISION_CONTRACT,
        "turn": int(turn),
        "proposals_considered": proposals_considered,
        "winning_proposal_id": winner.get("proposal_id"),
        "transition_type": transition_type,
        "accepted": True,
        "rejection_reason": "",
        "mission_before": deepcopy(mission_before),
        "mission_after": mission_after,
        "predecessor_mission": predecessor_mission,
        "topic_effect": winner.get("topic_effect"),
        "component": "mission_manager",
    }
