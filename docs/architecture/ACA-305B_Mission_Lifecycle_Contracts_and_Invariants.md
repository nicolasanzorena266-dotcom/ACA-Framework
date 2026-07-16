# ACA-305B - Mission Lifecycle Contracts and Invariants

Status: Conceptual design only. No code, class, or contract was created or
modified. No test was changed. No commit, no push.

Every claim about current code in this document was re-verified against the
working tree on 2026-07-16, in the same session that produced ACA-305A, with
no repository changes in between (`git status` is unchanged except for this
document and `CURRENT_STATE.md`).

## 0. Objective

Design the complete conceptual contract for `MissionManager` to evaluate
proposed mission transitions and apply exactly one atomic transition per
turn, while remaining — per ACA-305A's decision — the sole writer of
`active_mission`. This document is the design ACA-305A's §9 and §12
committed to producing next. It does not implement anything.

## 1. Scope

**In scope:** the conceptual data model for a mission transition proposal
and decision, the state machine and valid-transition table, the invariants,
ownership/idempotency/audit rules, how this integrates with the six
existing signals ACA-304/ACA-305A already found (`_advance_mission`,
`SemanticAuthority`, `TOPIC_SHIFT`, `mission_reevaluation`,
`abandonment_criteria`, `mission_impact.may_change_mission_state`), a
migration strategy from the current de facto mechanism, edge cases, risks,
and acceptance criteria for the implementation sprint (ACA-305C).

**Out of scope:** see §16.

## 2. Conceptual Data Model

Three conceptual objects, none of them a class yet:

1. **MissionTransitionProposal** — an inert value, produced by a component
   that observes evidence relevant to the mission. It requests a kind of
   change; it cannot cause one.
2. **MissionTransitionDecision** — produced only by `MissionManager`,
   evaluating zero or more proposals for the current turn. It is the only
   object whose existence can result in a write.
3. **Mission snapshot** — the existing `active_mission` dict shape
   (`type`, `goal`, `status`, `lifecycle_status`, `progress`, `next_act`,
   `blockers`, `missing`, plus type-specific fields such as `slots`/`facts`
   for `auto_claim_guidance`, `mission_manager.py:32-68`,
   `conversation_state.py:5504-5505`). This document does not change this
   shape; proposals and decisions reference it, they do not replace it.

Relationship: `N proposals -> 1 decision -> 0 or 1 write`. A turn may
produce zero proposals (nothing relevant happened), one, or several
(competing or complementary signals fired in the same turn — see §13).
Exactly one decision is produced per turn whenever `active_mission` is not
`None` at turn start or a proposal exists; that decision results in at most
one write.

## 3. Proposal Contract (`MissionTransitionProposal`)

### 3.1 Minimum fields

| Field | Type | Required | Purpose |
| --- | --- | --- | --- |
| `contract` | string | yes | `"mission_transition_proposal.v1"` |
| `proposal_id` | string | yes | Deterministic hash of `component` + `turn` + `transition_type` + evidence content. Enables deduplication (§10). |
| `component` | string | yes | Emitting component name, must be in the allowlist (§4). |
| `turn` | int | yes | `conversation_state.turn_count` at emission time. Must equal the current turn when evaluated (§7, §14). |
| `transition_type` | enum | yes | One of `maintain`, `complete`, `suspend`, `resume`, `replace`, `abandon` (§5). |
| `target_mission_type` | string or null | only for `replace` | The mission `type` being proposed. Null for every other transition type. |
| `mission_delta` | mapping | yes | The specific fields the proposer believes should change (e.g. `{"missing": [...], "blockers": [...]}`, or, for `auto_claim_guidance` today, exactly what `_advance_mission` already computes). **Never a full `active_mission` replacement dict** — see §8. |
| `evidence` | mapping | yes | Structured evidence bundle (§6). Never raw free text alone. |
| `confidence` | float, 0.0-1.0 | yes | Derived, not asserted (§7). |
| `reason` | string | yes | Short symbolic mechanism name, e.g. `"slots_answered_ready_to_progress"`, `"topic_shift_detected"`, `"abandonment_criterion_matched:new_unrelated_topic_detected"`. |

`mission_delta` and `target_mission_type` are the only fields that describe
*what changes*. Everything else describes *why* and *how sure*. No field
named `lifecycle_status`, `active_mission`, or `mission_after` may appear on
a proposal — see §8.

### 3.2 Who may emit proposals

| Component | Emits proposals for | Rationale |
| --- | --- | --- |
| `ConversationState` (`_advance_mission`, migrated per §14) | `maintain`, `complete` (once wired), `suspend`/`resume` (once wired) | Already computes fact/slot-driven mission content today; becomes the emitter instead of the de facto writer (ACA-305A §1.3-1.4). |
| `ConversationState` (`_mission_with_revision_clarification`) | `maintain` (toward `waiting_user`) | Same migration as above; already trace-shaped (`conversation_state.py:5430-5457`). |
| `ConversationState` (new: topic-shift evidence reader) | `maintain`, `resume`, `replace`, `abandon` | Reads `last_conversational_act` when `act == TOPIC_SHIFT` (`conversation_state.py:4157`) — a read `MissionManager` itself never performs today. |
| `ConversationState` (new: abandonment-criteria evaluator) | `abandon`, `replace` | Evaluates `abandonment_criteria` (`conversation_state.py:4220,4321`) against this turn's signals — currently declared, never evaluated (ACA-304 §4.2). |
| `ConversationState` (new: `mission_impact` reader) | filters eligibility, does not itself emit a distinct proposal (§14) | Gate: only `mission_impact.may_change_mission_state == True` turns are eligible to emit non-`maintain` proposals from goal/strategy evidence. |
| `SemanticAuthority` (via `semantic_authority_pilot`'s already-gated act/goal selection) | evidence input only, never a proposal on its own | Mission proposals consume the act/goal **already selected** by SA-3 (Legacy or Semantic); they do not re-adjudicate that choice (ACA-305A §11). |

### 3.3 Who may not emit proposals

| Component | Why excluded |
| --- | --- |
| `NarrativeResponseComposer`, `LLMVerbalizer`, `ObjectiveDeterministicRealizer`, `ConversationObjectiveProjector` | Output/language layer, strictly downstream of mission decisions. Allowing response generation to feed back into mission authority would create a generation-influences-state loop and violates "no LLM authority" (ACA-305A §8 invariant 6). |
| `operational_work_mapper.py` | Explicitly documented as a non-authoritative operational case view (ACA-019 precedent, ACA-305A §3). Must stay read-only. |
| `runtime_executor`, `legacy_runtime`, `memory_engine`, `context_manager` | Pure readers of `active_mission` today (ACA-305A §3); no evidence they should originate mission changes. |
| `IntentMatcher`, `ActionPlanner`, `FlowRouter`, `ExecutionPlan`, `DecisionGraphEngine` | Zero-cost/operational routing layer. Conflating "what flow runs this turn" with "what the mission is" would recreate a second planning authority (ACA-019 §9, "components that must not become operational authorities"). |
| Any tool, plugin, or domain pack | Matches ACA-019's existing precedent: "Plugins do not rank work globally and do not execute outside Runtime authority." |
| `PublicConversationProductLayer` | Its `reset()` path (`public_conversation_product_layer.py:426-428`) stays the explicit, manual, out-of-band clearing mechanism. It is not folded into this contract (§16). |

## 4. Decision Contract (`MissionTransitionDecision`)

Produced once per turn, only by `MissionManager`, generalizing the shape
already in production at `conversation_state.py:5521-5530` and the
`authority_mode`/`rollback_reason` pattern in `semantic_authority_pilot.py`.

| Field | Type | Purpose |
| --- | --- | --- |
| `contract` | string | `"mission_transition_decision.v1"` |
| `turn` | int | Current turn. |
| `proposals_considered` | list | Summaries (`component`, `transition_type`, `confidence`, `proposal_id`) of every proposal evaluated this turn, accepted or not. |
| `winning_proposal_id` | string or null | The accepted proposal's id, or null if none accepted. |
| `transition_type` | enum or `"none"` | What was actually applied. |
| `accepted` | bool | Whether any write occurred. |
| `rejection_reason` | enum or `""` | Populated only when `accepted == False`. Values enumerated in §15. |
| `mission_before` | mapping or null | Full prior mission snapshot, always preserved verbatim. |
| `mission_after` | mapping or null | Full resulting snapshot. Equals `mission_before` when rejected. |
| `predecessor_mission` | mapping or null | Only set on `replace`: the mission that was replaced, preserved in full (§12). |
| `evidence_considered` | mapping | The evidence bundles of every considered proposal, for audit (§11, §17). |
| `component` | string | Always `"mission_manager"` — the *decision* is always attributed to `MissionManager`, even though the *proposal* came from elsewhere. |

Structural rule mirrored from `semantic_authority_pilot.py:104-132`:
`MissionManager` computes `mission_after` itself from the accepted
proposal's `transition_type` + `mission_delta`, evaluated against the state
machine (§6). It never copies a `mission_after` field supplied by the
proposer, because no such field exists on the proposal contract (§3.1, §8).

## 5. Transition Types

| Type | Meaning | Effect on `active_mission` |
| --- | --- | --- |
| `maintain` | The mission continues; new evidence refines its content within the same type. | Mission dict updated in place; `type` unchanged. |
| `complete` | The mission's goal was achieved. | Mission dict updated, `lifecycle_status = COMPLETED`, retained (not cleared) so its facts remain available to memory/context. |
| `suspend` | The mission is paused, expected to possibly resume later. | Mission dict retained as-is, `lifecycle_status = SUSPENDED`. |
| `resume` | A suspended mission is reactivated. | Mission dict retained, `lifecycle_status` returns to an active state. Only legal when current `lifecycle_status == SUSPENDED`. |
| `replace` | The conversation now needs a different mission `type`. | Old mission preserved as `predecessor_mission` in the decision trace; a new mission dict is created for `target_mission_type`, starting at `INITIALIZED` — the same convention `MissionManager` already uses for first creation (`mission_manager.py:36,52,63`). |
| `abandon` | The system is giving up on the mission organically, with nothing to resume. | `active_mission` set to `None`. Distinct from `suspend`: there is no mission object left to resume; a later turn creating a mission goes through ordinary creation (`MissionManager.before_kernel`'s existing classification path), unchanged by this contract. |

`complete` and `suspend` both retain the mission dict (as opposed to
`abandon`, which clears it) specifically so the mission's accumulated
`facts`/`slots` remain addressable by `memory_engine` and `context_manager`
(both already read `active_mission` today — ACA-305A §3) after the mission
stops being active. This is a deliberate asymmetry, not an oversight.

## 6. State Machine and Valid Transition Table

`MissionLifecycleStatus` and `MISSION_LIFECYCLE`
(`conversation_state.py:65-122`) are **reused unchanged**. This document
adds a transition-type layer on top of the existing status graph; it does
not modify the graph.

| `transition_type` | Legal current `lifecycle_status` | Resulting `lifecycle_status` | Table basis |
| --- | --- | --- | --- |
| `maintain` | any except `COMPLETED` | one of `INITIALIZED`, `GATHERING_INFORMATION`, `READY_TO_PROGRESS`, `PROGRESSING`, `WAITING_USER` reachable from current per `MISSION_LIFECYCLE[current]` | Existing table, `conversation_state.py:86-121`; `COMPLETED`/`SUSPENDED` are deliberately excluded from `maintain`'s output so the mapping from transition type to target status stays unambiguous — reaching those two is only ever the result of a `complete`/`suspend` transition type, never a side effect of `maintain`. |
| `complete` | `READY_TO_PROGRESS`, `PROGRESSING` | `COMPLETED` | `MISSION_LIFECYCLE[READY_TO_PROGRESS]` and `[PROGRESSING]` both already legally include `COMPLETED` (`conversation_state.py:102,108`) — today unreachable only because nothing computes this target (ACA-305A §4.4). |
| `suspend` | any (including `COMPLETED`) | `SUSPENDED` | Every entry in `MISSION_LIFECYCLE` already legally allows `SUSPENDED` (`conversation_state.py:91,97,103,109,115`, plus `COMPLETED -> SUSPENDED` at line 117). |
| `resume` | `SUSPENDED` only | `GATHERING_INFORMATION` or `WAITING_USER` | The only two edges `MISSION_LIFECYCLE[SUSPENDED]` legally allows (`conversation_state.py:118-121`). Choice between the two mirrors `_mission_status_for`'s existing logic (missing slots -> `WAITING_USER`, otherwise -> `GATHERING_INFORMATION`). |
| `replace` | any | `INITIALIZED` (new mission, new `type`) | Not governed by `MISSION_LIFECYCLE` at all — it is establishing a new mission, not moving within the old one. Starts at `INITIALIZED`, matching `MissionManager`'s own creation convention. |
| `abandon` | any | n/a — `active_mission` becomes `None` | Not governed by `MISSION_LIFECYCLE`; terminal clearing, analogous to (but organically triggered, unlike) `PublicConversationProductLayer.reset()`. |

`_safe_mission_transition` (`conversation_state.py:5583-5588`) already
encodes a fallback rule for illegal `maintain`-style targets (force
`GATHERING_INFORMATION` when leaving `INITIALIZED`; otherwise stay put).
That fallback is preserved unchanged for `maintain`; `complete`, `suspend`,
and `resume` do not need it because §15 rejects an illegal request outright
rather than silently substituting a nearby legal one — a stricter rule than
today's `maintain`-only fallback, justified because these transition types
carry more consequence than an ordinary progress update.

## 7. Confidence

Confidence is always **derived from the confidence of the underlying
evidence**, never asserted fresh by the proposer:

- Fact/slot-driven evidence (today's `_advance_mission` path): confidence
  `1.0`. Facts reaching this stage are already confirmed
  (`_is_active_conversational_fact`, `conversation_state.py:5475-5480`);
  there is no second-guessing to represent.
- Conversational-act-driven evidence (`TOPIC_SHIFT`,
  `mission_reevaluation`): confidence equals the act's own recognition
  confidence, taken from whichever authority `semantic_authority_pilot`
  already selected for that act — never independently re-scored.
- Composite evidence (a proposal drawing on more than one signal):
  confidence is the **minimum** across contributing signals, not an
  average — a strong signal must not paper over a weak one.

Each `transition_type` declares its own minimum confidence threshold,
mirroring the differentiated per-signal thresholds already in
`semantic_authority_pilot.py` (`SEMANTIC_ACT_MIN_CONFIDENCE = 0.95`,
`SEMANTIC_GOAL_MIN_CONFIDENCE = 0.50`):

| `transition_type` | Suggested starting threshold | Rationale |
| --- | --- | --- |
| `maintain` | 0.50 | Matches the existing goal-confidence floor; low blast radius, easily corrected next turn. |
| `resume` | 0.65 | Reactivating a paused mission should require more than a bare guess, but is fully reversible via `suspend` again. |
| `suspend` | 0.65 | Pausing is reversible (`resume`); moderate bar. |
| `complete` | 0.75 | Terminal for this mission instance; higher bar than reversible transitions. |
| `replace` | 0.85 | High blast radius; starts an entirely new mission. |
| `abandon` | 0.85, plus corroboration (§9, §13) | Highest blast radius: clears the mission with nothing to resume. |

These are a starting point for ACA-305C to tune against the fixtures in
§17, exactly as `SEMANTIC_ACT_MIN_CONFIDENCE` was clearly benchmark-tuned
rather than derived analytically. They are not to be read as final values.

## 8. Preventing a Disguised Decision

This is the direct structural fix for the anti-pattern ACA-305A found
(§1.3-1.4 of the ADR: `_advance_mission` computes a finished mission dict
that `MissionManager` adopts by bare equality check). Rules:

1. **No proposal field may name a final state.** `MissionTransitionProposal`
   has no `active_mission`, `mission_after`, or `lifecycle_status` field
   (§3.1). It has `mission_delta` (the specific fields the proposer
   believes changed) and `transition_type` (the kind of change requested).
2. **Only `MissionManager` computes the result.** `mission_after` is
   derived by `MissionManager` from `mission_before` + `mission_delta` +
   `transition_type`, evaluated against §6's table — never copied from the
   proposal.
3. **No adoption by equality.** The current `MISSION_LOAD_FROM_
   CONVERSATION_STATE` branch (`mission_manager.py:17-21`), which adopts
   `conversation_state.active_mission` whenever it equals or replaces
   `current.active_mission`, is retired as a bypass. Every turn's mission
   state — including the bootstrap case where `conversation_state` already
   holds a mission before `CognitiveState` does — is evaluated as a
   proposal, even when the expected outcome is a trivial `maintain` that
   reaffirms existing state. There is no code path that adopts a mission
   value merely because it is present.
4. **The proposer cannot mark itself accepted.** No field on
   `MissionTransitionProposal` records an authority or acceptance
   judgment; that vocabulary (`accepted`, `rejection_reason`) exists only
   on `MissionTransitionDecision`.

## 9. Acceptance and Rejection Procedure

Per turn, `MissionManager.before_kernel`:

1. **Collect.** Gather every proposal emitted this turn (§3.2), deduplicate
   by `proposal_id` (§10).
2. **Validate structurally.** Reject outright (§15) anything with a missing
   required field, an unrecognized `component`, or an unrecognized
   `transition_type`.
3. **Resolve conflicts.** If more than one proposal survives validation,
   apply a fixed precedence order: `abandon > replace > complete > suspend
   > resume > maintain`. Same-type (`maintain`) proposals touching
   disjoint `mission_delta` fields are merged; same-type proposals
   disagreeing on the same field, or differently-typed proposals that
   cannot be resolved by precedence (e.g. two `replace` proposals naming
   different `target_mission_type`s), are rejected together as
   `unresolved_proposal_conflict` (§13, §15).
4. **Gate the winner.** Check, in order: `confidence >= transition_type`'s
   threshold (§7); the transition is legal from the current
   `(type, lifecycle_status)` per §6; for `abandon`/`replace`, at least one
   corroborating evidence item beyond a single low-specificity signal
   exists (§13); the evidence's `turn` matches the current turn (§14).
5. **Apply or reject.** If every gate passes: `MissionManager` computes
   `mission_after`, evolves `CognitiveState` with a new, distinguishable
   operation (`MISSION_TRANSITION`, replacing today's overloaded
   `MISSION_CREATE`/`MISSION_UPDATE`/`MISSION_LOAD_FROM_CONVERSATION_STATE`
   trio for this purpose — creation keeps `MISSION_CREATE` unchanged, §16),
   and records an accepted `MissionTransitionDecision`. If any gate fails:
   `mission_after = mission_before`, no write occurs, and a rejected
   `MissionTransitionDecision` is still recorded (§11) — rejection is
   observable, not silent.

A rejected proposal is not retried automatically within the same turn. If
the underlying condition persists, the emitting component naturally
re-emits an equivalent proposal next turn (the same way `_advance_mission`
already recomputes every turn today).

## 10. Idempotency Rules

- `proposal_id` is a deterministic function of `component`, `turn`,
  `transition_type`, and the evidence content (not a random or
  timestamp-based value — timestamps are unavailable in several parts of
  this codebase's tooling by design, and determinism is what makes
  deduplication possible at all). Two evaluations of the same underlying
  signal in the same turn must produce the same `proposal_id`.
- Before ranking (§9 step 3), `MissionManager` deduplicates by
  `proposal_id`; a proposal seen twice in one turn (re-entrant calls,
  retried step execution) is evaluated once.
- Exactly one write to `CognitiveState.active_mission` may occur per turn.
  This is a direct consequence of §8 (only `MissionManager` computes
  `mission_after`) and §9 (exactly one decision per turn) — it does not
  need a separate enforcement mechanism, only the discipline that no other
  call site is ever given `.evolve(...)` access to `active_mission` (§13).
- Re-submitting an already-accepted proposal (e.g. the mission is already
  in the target state) must be a legal `maintain` no-op — `mission_after ==
  mission_before`, `accepted = True`, `transition_type = "maintain"` — not
  an error. This preserves today's behavior where `_advance_mission`
  returns `None` (no advancement record) when nothing changed
  (`conversation_state.py:5519-5520`); the generalized contract represents
  that same case as an accepted no-op decision rather than the absence of
  one, so it stays observable (§11) instead of silently disappearing.

## 11. Audit Rules

- Every `MissionTransitionDecision` is recorded every turn a proposal
  existed or `active_mission` was non-null, whether accepted or rejected —
  generalizing the existing pattern where `_advance_mission`'s trace is
  only written when something changed (`conversation_state.py:5519-5530`).
  Under this contract, "nothing changed" becomes an accepted `maintain`
  no-op decision (§10), and "something was proposed but rejected" becomes
  a rejected decision — both are recorded, neither is silent.
- `mission_before` is never mutated in place; it is always a `deepcopy`
  snapshot, matching the existing convention in `_advance_mission`
  (`conversation_state.py:5492-5493`) and `_mission_with_revision_
  clarification` (`conversation_state.py:5437-5438`).
- `predecessor_mission` is retained in full on every `replace` decision
  (§4, §12) — a `replace` must never look, from the trace alone,
  indistinguishable from a `maintain` that happened to change many fields.
- Every rejection carries an enumerated `rejection_reason` (§15), never a
  free-text explanation only — enumerated values are what make Execution
  Trace and Introspection queryable (§18).

## 12. Preserving Prior State

- `mission_before` on every decision is sufficient to mechanically roll
  back the immediately preceding transition (§ ACA-305A invariant 8,
  restated here as the concrete mechanism: restore `mission_before` as the
  new `active_mission` via a `maintain` proposal with `mission_delta` equal
  to the full prior snapshot).
- `replace` additionally preserves the full outgoing mission as
  `predecessor_mission` on the decision (§4), so mission history survives
  a type change, not just a status change.
- This document does **not** propose a persistent, multi-turn
  `mission_history` list inside `ConversationState` — that would be a
  structural change to `ConversationState` (explicitly out of scope,
  ACA-305A §11 and CLAUDE.md). The natural home for longer-than-one-turn
  history, if ever needed, is the existing `topic_stack`, which already
  supports suspend/resume semantics for topics
  (`conversation_state.py:3353-3362`) and already stores a `mission_type`
  per topic (`_normalize_topic`, `conversation_state.py:4791-4812`). Noted
  as a possible future integration point, not a decision made here.

## 13. Ownership Rules

- `CognitiveState.active_mission` has exactly one writer:
  `MissionManager`, via `.evolve(...)`. This is unchanged from today
  (ACA-305A §3 confirmed it already holds) and is not weakened by this
  contract — proposals are, by construction (§8), incapable of writing.
- `ConversationState.active_mission` (the projection field, distinct from
  `CognitiveState`'s) continues to exist only as a projection, populated by
  `to_cognitive_state`/`project_from_cognitive_state`
  (`conversation_state.py:466-575`, `312-320`) — this document does not
  change that these are pure projections, only that the value being
  projected is now always one `MissionManager` decided, never one
  `ConversationState` computed and `MissionManager` merely mirrored.
- No component listed in §3.3 may be given `.evolve(...)` access to
  `active_mission` under any circumstance introduced by this contract.
- `PublicConversationProductLayer.reset()` remains the one exception,
  explicitly outside this contract (§16), because it already operates
  outside `ConversationState`/`MissionManager` entirely and is a manual,
  not organic, control.

## 14. Integration With Existing Components and Signals

| Existing element | Current role (ACA-304/ACA-305A evidence) | Role under this contract |
| --- | --- | --- |
| `ConversationState` | Computes fact/slot deltas, topic stack, conversational act/goal. | Unchanged as the place these are computed. Gains the responsibility of packaging relevant computations as proposals rather than as an adopted mission value. |
| `_advance_mission` | De facto co-decider for `auto_claim_guidance`, adopted by equality check (ACA-305A §1.3-1.4). | Becomes a `maintain`/`complete`-proposal emitter (§14 migration in §16). Its internal state-machine logic (`_mission_status_for`, `_next_act_for_mission`, `conversation_state.py:5533-5560`) is reused as the basis for computing `mission_delta`, not discarded. |
| `SemanticAuthority` | Computes a candidate conversational act/goal, gated into or out of authority by `semantic_authority_pilot.py`. | Mission proposals consume the **already-selected** act/goal (Legacy or Semantic, per SA-3's existing gate) as evidence. This contract adds no second semantic adjudication and does not reopen SA-3's scope (`LOW_RISK_SEMANTIC_ACTS = {"greeting"}`, `semantic_authority_pilot.py:17`), per ACA-305A §11. |
| `TOPIC_SHIFT` | Real act category; only ever mutates `topic_stack` (`conversation_state.py:3353-3362`); never read by `MissionManager`. | Becomes a recognized `evidence_kind`. `direction == "new_topic"` is candidate evidence for `replace`/`abandon`; `direction in {"resume_previous","indirect_previous"}` is candidate evidence for `resume`/`maintain` — deliberately mirroring topic-level suspend/resume semantics that already work today, rather than inventing new ones. |
| `impact.mission_reevaluation` | Set `True` on `PENDING_ANSWER`/`CORRECTION` acts (`conversation_state.py:3941,3961`); never read. | Becomes the trigger that tells `ConversationState` "attach mission-directed evidence to this turn's proposal set at all" — a switch that gates *whether to look*, not a transition type by itself. |
| `abandonment_criteria` | Declared per-goal (`conversation_state.py:4220,4321`); never evaluated. | A new evaluator (living in `ConversationState`, called during the same pass that already computes conversational goals) checks the active mission's declared criteria against this turn's signals and, when satisfied, emits an `abandon` or `replace` proposal with `evidence_kind = "abandonment_criterion"`. |
| `mission_impact.may_change_mission_state` / `preserve_active_mission` | Computed by `_mission_impact_for` (`conversation_state.py:4366-4381`); never read. | Becomes an eligibility filter: goal/strategy-sourced evidence may only propose something other than `maintain` when `may_change_mission_state == True` for that turn's selected strategy. |

## 15. Errors That Must Force Safe Rejection

| Condition | `rejection_reason` |
| --- | --- |
| Missing/malformed required proposal field | `malformed_proposal` |
| `component` not in the allowed-emitter list (§3.2) | `unauthorized_emitter` |
| `transition_type` not one of the six known values | `unknown_transition_type` |
| `confidence < transition_type`'s minimum threshold (§7; comparison direction matches `semantic_authority_pilot.py`'s existing `<` check) | `confidence_below_threshold` |
| Transition illegal from current `(type, lifecycle_status)` per §6 | `illegal_transition` |
| Evidence `turn` does not match the current turn | `stale_evidence` |
| Exception raised while evaluating a proposal | `proposal_evaluation_exception` (mirrors `semantic_authority_pilot.py:82-86`'s try/except pattern exactly) |
| Unresolved conflict between proposals (§9 step 3, §13 edge case) | `unresolved_proposal_conflict` |
| `abandon`/`replace` with only one low-specificity corroborating signal | `insufficient_corroboration` |
| `replace` where `target_mission_type` equals the current `type` | `replace_target_equals_current_type` (degenerate — caller should have used `maintain`) |
| `abandon`/`replace`/`suspend`/`resume`/`complete` targeting a mission already in `COMPLETED` and requesting anything but `suspend` | `mission_already_terminal` |

Every rejection leaves `mission_after == mission_before`, byte-for-byte,
and is still recorded (§11) — rejection is a normal, observable outcome,
not a failure to be hidden.

## 16. Compatibility With Existing Code and Migration Strategy

### 16.1 What does not change

- `MissionManager` remains the sole `active_mission` writer (§13).
- Mission **creation** (`MissionManager.before_kernel`'s keyword
  classification, `mission_manager.py:28-69`) is untouched. This contract
  governs transitions of an *existing* mission; creation of the first
  mission is a distinct, already-working mechanism (§17 edge case notes
  this explicitly for 305C).
- `ConversationState`'s field shape, `MISSION_LIFECYCLE`, and
  `MissionLifecycleStatus` are all reused unchanged (§6).
- `PublicConversationProductLayer.reset()` stays outside this contract —
  it is a manual UI action in the public/legacy adapter layer, not
  organic mission understanding, and ACA-305A explicitly left it alone.
- The Semantic Authority promotion gate's scope is untouched (§14, §3.2).

### 16.2 Migration stages for `_advance_mission`

Mirroring ACA-019's phased migration pattern (freeze -> shadow -> controlled
adoption -> alignment -> legacy removal) and HANDOFF.md's shadow ->
benchmark -> gated-selector -> rollback discipline:

1. **Stage 0 (shadow).** `_advance_mission` keeps computing exactly as it
   does today. It additionally emits a `MissionTransitionProposal`
   wrapping the same delta. `MissionManager`'s new gate runs alongside the
   existing `MISSION_LOAD_FROM_CONVERSATION_STATE` adoption path, computing
   what it *would* decide, logging any divergence, but not yet replacing
   the current write. No behavior change.
2. **Stage 1 (gated, single path).** The gate becomes authoritative only
   for `auto_claim_guidance` `maintain` proposals — the one path already
   proven end-to-end (ACA-305A §1.3). The `MISSION_LOAD_FROM_CONVERSATION_
   STATE` equality-check branch is removed for this case. Acceptance bar:
   byte-identical `active_mission` output to today's behavior across the
   existing test suite and benchmarks (a pure authority refactor, not a
   behavior change).
3. **Stage 2 (extend coverage).** Add the `general_orientation` `maintain`
   ruleset (mirroring `_mission_status_for`/`_next_act_for_mission`'s
   shape but for `user_need`, the only slot that mission type tracks).
   Wire `TOPIC_SHIFT`, `abandonment_criteria`, and
   `mission_impact.may_change_mission_state` as new proposal sources, each
   independently shadowed and benchmarked before being trusted — the same
   per-signal discipline SA-3 already used per conversational act.
4. **Stage 3 (unlock terminal/lateral transitions).** Enable `complete`,
   `suspend`, `resume`, `replace`, `abandon` only once Stage 2's evidence
   sources are stable and benchmarked. This is the highest-risk stage and
   is sequenced last deliberately.

### 16.3 Execution-trace and operation-name compatibility

`MISSION_CREATE` and `MISSION_UPDATE` (`execution_trace.py:367-368`) are
kept for what they already correctly describe (creation, and the
`after_kernel` progress bump). A new operation, `MISSION_TRANSITION`, is
introduced for decisions produced by this contract, and must be added to
`_component_for_operation`'s mapping (`execution_trace.py:357-378`) as
`mission_manager` — alongside a corrected mapping for
`MISSION_LOAD_FROM_CONVERSATION_STATE`, which currently falls through to
`"runtime"` instead of `"mission_manager"` (a small, already-identifiable
bug independent of this migration, worth fixing at the same time since the
gate touching this code path will already be under review).

## 17. Edge Cases

1. **Two `maintain` proposals in the same turn touching disjoint fields**
   (e.g. fact-driven `blockers` update and topic-driven `next_act`
   suggestion) are merged field-by-field; only same-field disagreement is
   a conflict (§9, §15).
2. **`resume` when `lifecycle_status != SUSPENDED`** — illegal, rejected
   (`illegal_transition`), no-op.
3. **`abandon`/anything-but-`suspend` targeting an already-`COMPLETED`
   mission** — rejected (`mission_already_terminal`); a completed mission
   may only additionally transition to `suspend` per the existing table
   (`MISSION_LIFECYCLE[COMPLETED] = (SUSPENDED,)`,
   `conversation_state.py:117`).
4. **No `active_mission` exists (`None`) and a proposal arrives** —
   proposals under this contract only apply to an *existing* mission.
   Creation is untouched (§16.1). A proposal arriving with no mission to
   transition is rejected (`illegal_transition`); 305C must not conflate
   "create" and "transition."
5. **A single turn contains both an abandon-worthy signal and ongoing
   progress on the current mission** (e.g. an explicit disengagement
   phrase in the same message as a slot answer) — resolved deterministically
   by the precedence order (§9 step 3: `abandon > ... > maintain`), but
   flagged here as a case that needs its own benchmark fixture (§17.6 in
   §18 below), not merely assumed correct by construction.
6. **Confidence exactly at threshold** — accepted (`>=`), matching the
   comparison direction already used in `semantic_authority_pilot.py`.
7. **`replace` where `target_mission_type` equals the current `type`** —
   rejected as degenerate (`replace_target_equals_current_type`); callers
   must use `maintain` for same-type changes.
8. **Stale/replayed evidence** — a proposal whose `turn` does not match
   the current turn is rejected (`stale_evidence`), preventing a delayed
   or re-entrant computation from being accepted late.
9. **A rejected proposal followed by an identical proposal next turn** —
   not a special case; it is evaluated fresh, exactly like today's
   per-turn recomputation of `_advance_mission`.

## 18. Risks

| Risk | Description | Mitigation |
| --- | --- | --- |
| Scope creep into detection quality | Wiring `TOPIC_SHIFT`/`abandonment_criteria` might tempt fixing the underlying lexical-whitelist narrowness (ACA-304 §4.1) in the same sprint. | Explicitly out of scope (§19); Option 2 from ACA-304 stays its own, separately-sequenced Semantic Firewall package. |
| Recreating a second authority | If `_advance_mission` (or any new evaluator) is allowed to keep writing directly "just this once" during migration, the exact ACA-305A §1.4 problem reappears. | Stage 1 of §16.2 removes the equality-check adoption path in the same step it gates the first real path — there is no intermediate state where both a proposal-gate and a direct-write path coexist for the same signal. |
| Threshold values are guesses | §7's suggested confidence thresholds are not empirically derived. | Explicitly flagged as a 305C tuning task against the fixtures in §17 (this doc) / acceptance criteria (§20), not a final decision. |
| `abandon` over-triggering | A single ambiguous message (e.g. "Ninguno" alone, from ACA-304's reproduction) must not clear a mission on a hair-trigger. | `insufficient_corroboration` gate (§9 step 4, §15) requires more than one low-specificity signal for `abandon`/`replace`. |
| Observability lag | If Execution Trace/Introspection wiring (§21) lags the contract's implementation, rejected decisions become invisible again, recreating a version of the exact "write-only signal" pattern this whole effort is trying to close. | §21 is listed as part of ACA-305C's acceptance criteria (§20), not an optional follow-up. |
| `replace`/`abandon` interacting with `topic_stack` inconsistently | `topic_stack` already has its own suspend/resume semantics (`conversation_state.py:3353-3362`) that this contract deliberately mirrors but does not merge with. A `replace`/`abandon` mission transition that leaves `topic_stack` in a contradictory state (e.g. mission cleared but topic still marked active) is possible if the two are wired independently. | 305C must specify (not this document — it would be a `ConversationState` structural decision, out of scope here) whether/how a mission-level `replace`/`abandon` should also emit a corresponding topic-stack update, or explicitly document that they are allowed to diverge for one turn and reconcile next turn. |

## 19. Acceptance Criteria for ACA-305C

ACA-305C (implementation) is ready to begin only once:

1. The proposal and decision shapes in §3-§4 are translated into real
   contracts (dataclasses or equivalent), with the field lists in this
   document as the source of truth.
2. Stage 1 of the migration (§16.2) is implemented and passes the existing
   test suite and benchmarks with byte-identical `active_mission` output
   for every `auto_claim_guidance` scenario currently covered.
3. The fixtures below exist in the benchmark corpus and are wired to run
   before any Stage 2/3 promotion:
   - The exact ACA-304 reproduction (`Hola` / `¿Cómo estás?` / `Mis
     vacaciones` / `Ninguno` / `¿Dios existe?`), with an acceptance bar of
     *"produces at least one non-`maintain`-trivial, non-rejected
     `MissionTransitionDecision` by turn 3"* — not full human-quality
     resolution, which depends on the separately-scoped detection-quality
     work (ACA-304 Option 2).
   - A `complete` fixture: a scripted `auto_claim_guidance` conversation
     where all required facts/slots resolve, asserting
     `lifecycle_status == COMPLETED` is actually reached (impossible
     today per ACA-305A §4.4).
   - A `suspend`/`resume` fixture: an explicit subject change mid-mission
     followed by an explicit return, asserting the *same* mission (not a
     fresh one) resumes with its facts intact.
   - An `abandon` fixture: a clear, corroborated disengagement (not a
     single ambiguous word), asserting `active_mission` becomes `None`
     and a fresh mission can be created cleanly next turn.
   - A conflict fixture exercising §9 step 3's precedence rule with two
     proposals in one turn.
   - A rejection fixture asserting a sub-threshold proposal leaves
     `active_mission` byte-for-byte unchanged and produces a visible
     rejected decision in Execution Trace and Introspection.
4. Execution Trace (`MISSION_TRANSITION` operation, corrected
   `MISSION_LOAD_FROM_CONVERSATION_STATE` attribution) and Runtime
   Introspection (a `mission_decision` snapshot key mirroring the existing
   `_output_decision_summary` pattern, `introspection.py:171,176`) both
   expose every decision, accepted or rejected, without needing to
   reconstruct it from raw `facts`.
5. None of §16.1's "what does not change" items have been violated by the
   design produced in step 1.

## 20. Explicitly Out of Scope

- Any code, class, dataclass, or contract implementation. This document is
  conceptual only, per the session's explicit instruction.
- Any test change.
- Improving topic/relevance **detection** quality (ACA-304 Option 2,
  the lexical-whitelist narrowness in `_mentions_topic_shift` and
  `SemanticAuthority`'s own topic-shift markers). Remains sequenced under
  the Semantic Firewall roadmap (ACA-100), independent of this contract.
- Reopening `semantic_authority_pilot.py`'s promotion scope
  (`LOW_RISK_SEMANTIC_ACTS = {"greeting"}`). This contract consumes
  whatever SA-3 already selects; it does not ask SA-3 to select more.
- Restructuring `ConversationState`'s fields, including not introducing a
  persistent multi-turn `mission_history` list (§12).
- Deciding whether `_advance_mission`'s computation physically moves into
  `MissionManager` or stays in `ConversationState` and is called from it —
  left open in ACA-305A §11 and still left open here; §16.2's migration
  stages work identically either way, and 305C should decide this as an
  implementation detail informed by whichever is less invasive at that
  time, not as an authority question.
- Reconciling `topic_stack` and mission-level `replace`/`abandon`
  transitions beyond flagging the risk (§18) — a `ConversationState`
  design decision for 305C, not an authority question this document
  answers.
- Any change to `PublicConversationProductLayer.reset()` or the manual
  `reset_conversation` UI action.
- Any change to the LLM Verbalization / Conversational-First output layer
  currently uncommitted in the working tree. Confirmed again during this
  session's evidence check to have no mission-authority surface.
- Promoting Candidate Work / Operational Governance / Operational Audit
  Ledger from Shadow.
- Tuning the confidence thresholds in §7 to final values — flagged as a
  305C benchmark task, not decided here.

`CURRENT_STATE.md` is updated separately, reflecting that this design is
closed with no ambiguous contract decisions remaining, except the two
explicitly and deliberately left open in §20 (physical location of
`_advance_mission`'s logic; `topic_stack` reconciliation), both of which
are implementation-detail questions rather than authority questions and do
not block ACA-305C from starting.
