# ACA-305D - Mission Lifecycle Minimal Controlled Implementation

Status: **CLOSED.** All six ACA-305C fixtures pass. Full suite: 736/736
green (730 pre-existing tests, zero regressions, plus the six fixtures).
Single-writer, one-transition-per-turn, and observability invariants
verified. See section 10 for the closing sprint's work (built on the
ACA-305D-RC1/RC2/RC3 audits and implementation below) and final results.

No commit, no push. `CURRENT_STATE.md` is updated to reflect closure.

## 1. Summary (Original Implementation Pass -- Superseded by Section 10)

*The table below reflects the state after the first ACA-305D implementation
pass, before ACA-305D-RC1/RC2/RC3 and the closing sprint. Kept for the
historical record. Section 10 has the final, current state.*

| Sprint requirement | Status (original pass) |
| --- | --- |
| Six ACA-305C fixtures added, red-verified before any Runtime change | Done |
| `SWITCH_TOPIC` semantics corrected | Done |
| `MissionTransitionProposal`/`MissionTransitionDecision` introduced | Done |
| `MissionManager` gates, decides, applies at most one transition/turn | Done |
| `_advance_mission` migrated to proposal emitter, byte-identical | Done, verified |
| `general_orientation` + `TOPIC_SHIFT` wired | Done (TOPIC_SHIFT only; see section 5 for what was deliberately not wired) |
| Mission <-> `topic_stack` integration (suspend/resume) | Done, verified (fixture 6) |
| Topic id collision (`mission:{type}`) fix | **Deferred** -- unreachable in this implementation (see section 5) |
| Observability (Introspection + Execution Trace) | Done |
| Fixtures pass | **4 of 6 fail** (fixtures 1, 2, 3, 4) |
| Full suite green | **732 passed, 4 failed** -- all 4 failures are the above fixtures; all 730 pre-existing tests pass, zero regressions |
| `MissionManager` sole writer of `active_mission` | Verified, holds |
| At most one transition decision per turn | Verified by construction |
| Every acceptance/rejection audited | Done |
| Byte-identical `auto_claim_guidance` | Verified (fixture 5 + zero regressions across 730 pre-existing tests) |

At the time this table was written, the sprint was not closed. It has since
been closed -- see section 10.

## 2. What Was Implemented

### 2.1 Fixtures (`tests/test_aca_305_mission_lifecycle_fixtures.py`)

All six ACA-305C fixtures were implemented as executable tests against the
real Runtime (`sdk.factory.build_galicia_runtime`, matching ACA-304's
reproduction method), run once before any Runtime change to confirm each
failed for the exact documented reason, per the sprint's mandatory order
(step 2). Two corrections were made to the fixtures' own message sequences
during that red-verification pass, based on direct evidence gathered by
running them:

- Fixture 3's original sequence fed the assistant's own multiple-choice
  question back in as if it were user input. Corrected to the actual
  ACA-304 sequence (`"Hola"` -> `"¿Cómo estás?"` -> `"Ninguno"`), since the
  multiple-choice question is a *system response*, not something a user
  would type.
- Fixture 4 was similarly corrected to a direct two-turn sequence
  (`"Me chocaron el auto"` -> `"¿Dios existe?"`), matching the sprint
  brief's literal wording ("misión de seguros -> ¿Dios existe?").

Fixture 2's and Fixture 6's assertions were also sharpened after an initial
red-verification pass revealed the first draft of each was too weak to
actually catch the documented defect (see section 4 of the transcript for
the diagnostic evidence): fixture 2 now checks specifically that
`"mis vacaciones"` is not absorbed verbatim as the `user_need` slot value
(the precise mechanism, not just "the response text differs"); fixture 6
now checks that the mission's own `lifecycle_status` becomes `suspended`
in the same turn the topic is suspended (the precise coherence invariant),
not merely that the mission "still exists" afterward -- an early version of
fixture 6 passed for the wrong reason (the mission was never suspended in
the first place, so trivially "recovering" it proved nothing).

### 2.2 `SWITCH_TOPIC` correction (`aca_os/conversation_state.py`)

`_mission_impact_for` (line ~4366) previously placed `SWITCH_TOPIC` in
`preserve_active_mission`'s set and excluded it from
`may_change_mission_state`'s set -- asserting the opposite of what
ACA-305C's integration decision requires. `SWITCH_TOPIC` was moved into
`may_change_mission_state`'s eligible set, with `preserve_active_mission`
left correct for lateral, non-mission-affecting strategies (`SIMPLIFY`,
`SUMMARIZE`, `DEEPEN`, `CONTINUE`, `ASK_CLARIFICATION`, `REPAIR` all remain
unchanged in `preserve_active_mission`, per the sprint's instruction to
"preservar las garantías existentes para cambios laterales que no
impliquen misión"). Confirmed by full-suite run: zero regressions from
this change alone (the field was, and outside the new code below remains,
unconsumed by anything else).

### 2.3 `MissionTransitionProposal` / `MissionTransitionDecision`

Implemented as plain dict-shaped contracts (matching this codebase's
existing convention -- `_advance_mission`'s trace dict,
`semantic_authority_pilot.py`'s decision dict -- rather than introducing a
new class hierarchy):

- **Proposal fields** (`aca_os/conversation_state.py`,
  `_mission_transition_proposal_from_advancement` and
  `_topic_shift_mission_proposal`): `contract`, `proposal_id`, `component`,
  `turn`, `transition_type`, `target_mission_type`, `mission_before`,
  `mission_delta`, `evidence`, `confidence`, `reason`, and (topic-driven
  proposals only) `topic_effect`. **No proposal carries a `mission_after`
  field** -- the anti-disguised-decision rule from ACA-305B section 8 is
  enforced structurally: proposals describe a delta and a requested
  transition kind; only `MissionManager` computes a result.
- **Decision fields** (`aca_os/mission_manager.py`,
  `evaluate_mission_transition_proposals`): `contract`, `turn`,
  `proposals_considered` (every proposal seen this turn, valid or not),
  `winning_proposal_id`, `transition_type`, `accepted`, `rejection_reason`
  (one of `malformed_proposal`, `unauthorized_emitter`,
  `unknown_transition_type`, `stale_evidence`,
  `confidence_below_threshold`, `illegal_transition`,
  `unresolved_proposal_conflict`, `mission_already_terminal`,
  `replace_target_equals_current_type`, or `""` when accepted),
  `mission_before`, `mission_after`, `predecessor_mission` (set only for
  `replace`), `topic_effect`, `component` (always `"mission_manager"`).

### 2.4 `MissionManager` as sole evaluator/writer (`aca_os/mission_manager.py`)

`before_kernel`'s prior equality-check adoption
(`if conversation_state.active_mission == current.active_mission: ...`,
ACA-305A section 1.3) is replaced by
`evaluate_mission_transition_proposals`, which:

1. Collects every proposal from `conversation_state.derived_state
   ["mission_transition_proposals"]`, deduplicating by `proposal_id`.
2. Validates each structurally (allowed `component`, known
   `transition_type`, matching `turn`).
3. Resolves multiple candidates by the fixed precedence order
   `abandon > replace > complete > suspend > resume > maintain`
   (ACA-305B section 9 step 3), merging same-type `maintain` proposals
   with disjoint delta fields and rejecting them together
   (`unresolved_proposal_conflict`) on a genuine field disagreement.
4. Gates the winner: `mission_already_terminal` check, degenerate-`replace`
   check, confidence-vs-threshold check (ACA-305B section 7's starting
   values, unchanged), then legality against the reused, unmodified
   `MISSION_LIFECYCLE` table (ACA-305B section 6's mapping).
5. Computes `mission_after` itself -- `{**mission_before, **mission_delta}`
   for `maintain`/`complete`/`suspend`/`resume`; `None` for `abandon`;
   the delta taken as a full new mission dict for `replace` -- and is the
   only code path that calls `CognitiveState.evolve(..., active_mission=
   ...)` for anything beyond initial creation (`MISSION_CREATE`, unchanged)
   and the progress bump (`MISSION_UPDATE`, unchanged). A new operation,
   `MISSION_TRANSITION`, was introduced for this decision and registered
   in `execution_trace.py`'s `_component_for_operation` map, alongside a
   correction for `MISSION_LOAD_FROM_CONVERSATION_STATE`, which previously
   fell through to `"runtime"` instead of `"mission_manager"`.

### 2.5 `_advance_mission` migration (`aca_os/conversation_state.py`)

`_advance_mission`'s internal computation (the `auto_claim_guidance`
lifecycle state machine -- `_mission_status_for`, `_next_act_for_mission`,
`_mission_progress_for`, `_safe_mission_transition`) is **unchanged**, per
ACA-305C's own explicit deferral of "where this logic physically lives" to
implementation discretion. What changed is only what happens to its
output: `assimilate_user_facts` still applies it to `ConversationState`'s
own working copy of `active_mission` (needed for the same turn's downstream
slot/plan computations, unchanged from before), but now additionally
packages it as an inert `MissionTransitionProposal`
(`_mission_transition_proposal_from_advancement`) carrying `mission_before`
+ a `mission_delta` (the exact fields `_advance_mission` set) rather than a
final `mission_after`. `MissionManager` reconstructs `mission_after` from
that proposal's own `mission_before`/`mission_delta` pair -- not from
`current.active_mission` (which, per ACA-305A section 1.3's traced call
order, already reflects the same-turn advancement by the time
`MissionManager.before_kernel` runs, so using it as the merge base would
double-apply the delta). This byte-identical reconstruction was verified
by: (a) fixture 5 passing, (b) zero regressions across all 730 pre-existing
tests, many of which exercise `auto_claim_guidance` multi-turn flows.

### 2.6 Mission <-> `topic_stack` integration (`aca_os/conversation_state.py`)

`update_topic_stack` gained one new call, `_topic_shift_mission_proposal`,
invoked once per turn with whatever `suspended_topic`/`resumed_topic` that
turn's existing topic-navigation logic already produced (no change to
`update_topic_stack`'s own topic-decision logic). When the affected topic
is mission-backed (`id == "mission:{active_mission.type}"`), it emits a
`suspend` or `resume` proposal mirroring the topic transition, carrying the
conversational act's own confidence as evidence and a `topic_effect`
sub-record (topic id, from/to status, `"mirrors_mission_transition:
{type}"` reason) that flows through into the resulting
`MissionTransitionDecision`.

This is a deliberate, evidenced adaptation of ACA-305C's originally-
described ordering (mission decision -> topic effect): because
`update_topic_stack` already runs, and already decides topic status,
*before* `MissionManager` runs in the existing turn pipeline (traced via
`ConversationManager.begin_turn`'s call order), the topic side is the
practical evidence *source* for the mission proposal in this
implementation, not a downstream *effect* of it. `MissionManager` still
makes the actual mission decision (accept/reject/threshold-check), and the
topic side is never written by `MissionManager` -- ownership stays exactly
as ACA-305C section 2.2 specified. This was the one point where the
concrete pipeline ordering required an implementation choice ACA-305C had
left open; it is recorded here rather than silently decided.

Verified end-to-end by fixture 6, which failed red before this change
(mission's `lifecycle_status` stayed `waiting_user` while its topic went
`suspended`) and passes after it (mission reaches `lifecycle_status ==
suspended` in the same turn the topic suspends, and both mission and topic
coherently return to active/resumed together on `"volvamos a la
denuncia"`).

### 2.7 Observability

- `aca_os/introspection.py`: `_state_summary` gained a `mission_decision`
  key, populated by `_mission_decision_summary` reading
  `state.facts["mission_transition_decision"]` -- mirroring the existing
  `output_decision`/`_output_decision_summary` pattern exactly, per
  ACA-303's own established convention.
- `aca_os/execution_trace.py`: `_component_for_operation` gained
  `MISSION_TRANSITION` and `MISSION_LOAD_FROM_CONVERSATION_STATE` (the
  latter was previously missing entirely, defaulting to `"runtime"`).
- `aca_os/session.py`: `_canonical_operations_for_compare` (used by
  `ExecutionSession.compare` for cross-session stability checks) already
  hardcoded `MISSION_LOAD_FROM_CONVERSATION_STATE` as canonically
  equivalent to `MISSION_CREATE`, for exactly the "same input processed
  twice should show stable operations" case this new code path also
  produces. `MISSION_TRANSITION` was added to that same equivalence rule.
  This was discovered as a real, if narrow, regression during full-suite
  verification (section 3) and is now fixed.

## 3. Regression Found and Fixed During Verification

`test_execution_session_compare_reports_stable_decisions`
(`tests/test_execution_session.py`) failed on the first full-suite run
after the `MissionManager` gate landed. Diagnosis (reproduced by
temporarily stashing `mission_manager.py` to compare old vs. new operation
traces for the same scripted input): `ExecutionSession.compare`'s
stability check normalizes `MISSION_LOAD_FROM_CONVERSATION_STATE` to
`MISSION_CREATE` before comparing two sessions' operation sequences, a
pre-existing accommodation for exactly the "turn 2 of a repeated identical
message reaffirms the same mission" case. Introducing `MISSION_TRANSITION`
as a new, more precise operation name for that same case broke this
existing normalization. Fixed by adding `MISSION_TRANSITION` to the same
equivalence rule (`aca_os/session.py`). Re-verified: `test_execution_
session.py`'s full file and the complete suite both pass after the fix,
with zero other regressions found across two full-suite runs.

This is exactly the kind of coupling "cambios pequeños, verificables y
reversibles" and "ejecutá tests después de cada bloque relevante" are
meant to catch before it compounds -- recorded here as evidence those
practices were followed, not skipped.

## 4. Why Fixtures 1, 2, and 3 Remain Red

All three trace to the same root mechanism, evidenced by direct diagnostic
runs against the Runtime during this sprint (not inferred):

- **Fixture 1** (`"Hola"` -> `"¿Cómo estás?"`): the response is still the
  `auto_claim_guidance`-flavored multiple-choice reformulation
  ("...el arreglo, la denuncia, la documentación o los tiempos?").
- **Fixture 2** (`"Necesito ayuda"` -> `"Mis vacaciones"`): `"mis
  vacaciones"` is still stored verbatim as the `user_need` slot's value.
- **Fixture 3** (`"Hola"` -> `"¿Cómo estás?"` -> `"Ninguno"`): the third
  turn's response is still byte-identical to the second turn's.

The mechanism responsible is `resolve_pending_slot_answers`
(`conversation_state.py:941-1016`), which is called from
`ConversationManager.begin_turn` (line 203) *before* `assimilate_user_facts`
and *before* `update_topic_stack` -- upstream of every proposal-emission
point this sprint added. It matches an incoming message against a pending
slot's question via `_explicit_slot_matches`/`_contextual_slot_match`, and
for `general_orientation`'s single, low-specificity `user_need` slot, the
"contextual" match branch accepts essentially any non-empty message as an
answer. **This is a fourth mission-content-writing site this sprint's
implementation work surfaced that ACA-305A/B/C's writer audit did not
specifically name** (it writes `ConversationState.active_mission` via
`_mission_with_slots`, not `CognitiveState.active_mission` directly, so it
does not violate the single-CognitiveState-writer invariant verified in
section 6 -- but it is the actual, upstream source of the slot-absorption
behavior these three fixtures target, and it runs before any of this
sprint's proposal-emission points ever see the turn).

Correcting `_explicit_slot_matches`/`_contextual_slot_match`'s matching
precision is squarely the "cognitive" / detection-quality dimension
ACA-304 section 5 classified as **contributing, not primary**, and which
ACA-304 section 7 (Option 2), ACA-305B section 20, and ACA-305C section 13
all independently and explicitly scoped out of the mission-*authority*
work this sprint implements -- sequenced instead under the Semantic
Firewall roadmap (ACA-100). This sprint's rules also explicitly forbid
promoting `SemanticAuthority` "más allá de lo ya aprobado," which a
relevance-aware rewrite of slot matching would risk doing without its own
shadow/benchmark/gated-promotion cycle.

**This is a real tension the sprint brief did not resolve in advance**: its
acceptance criteria state fixtures 1-3's outcomes as unconditional
("no activa orientación de seguros," "no repite la misma pregunta"), while
ACA-304/305B/305C -- documents this same sprint brief requires reading and
contrasting against code first -- already flagged detection-quality work as
out of scope for the mission-authority track. Given that conflict, and
given this sprint's explicit instruction to prefer small, reversible,
verifiable changes over broad architecture changes, the choice made here
was not to reach into `resolve_pending_slot_answers`'s matching logic. That
choice is what leaves fixtures 1-3 red. The alternative -- editing
detection/matching logic without its own shadow/benchmark discipline --
was judged the larger risk, and is flagged for an explicit decision rather
than taken unilaterally.

## 5. Why Fixture 4 Remains Red, and What Was Deliberately Not Wired

`"¿Dios existe?"` against an `auto_claim_guidance` mission does not match
any existing lexical `TOPIC_SHIFT` trigger (`_mentions_topic_shift`'s
whitelist requires phrases like "cambiemos de tema") and does not touch
`resolve_pending_slot_answers`' pending-slot matching either (there is no
open slot question it could be misread as answering, unlike fixtures 1-3).
The `abandonment_criteria` field this sprint's contract was designed to
consume (ACA-305B section 3.2, ACA-305C section 1.4) is declared but
requires a relevance judgment ("is this message unrelated to the active
mission?") to evaluate meaningfully -- and building that judgment is, again,
detection-quality work (ACA-304 Option 2), not authority work. No
`abandonment_criteria` evaluator was implemented for this reason; wiring a
fake or trivial one (e.g., "always true") would violate "no cambies
arquitectura fuera del alcance" in the opposite direction, by inventing
detection behavior no evidence supports.

**What was, and was not, wired for `general_orientation`/mission-wide
signal consumption (sprint step 8):**

- `TOPIC_SHIFT` consumption: **wired**, generically, for any mission type
  (section 2.6) -- this is what makes fixture 6 pass, and is real, tested,
  evidence-driven wiring, not a stub.
- `mission_reevaluation` (the `impact.mission_reevaluation` flag on
  `PENDING_ANSWER`/`CORRECTION` acts): **not wired**. Per ACA-305C section
  14, this flag's intended role is to gate *whether to look* for mission-
  relevant evidence, not to itself constitute evidence. Wiring it without
  a corresponding relevance evaluator (the same gap as `abandonment_
  criteria`, above) would not have changed observable behavior.
- `abandonment_criteria`: **not wired**, per this section.
- `mission_impact.may_change_mission_state`: **wired** as a semantic
  correction (section 2.2) but not yet consumed as an eligibility filter
  by any new code (the `TOPIC_SHIFT` path in section 2.6 does not
  currently read it, since it runs before `apply_conversational_goal`
  computes it -- see section 2.6's ordering note). It is real,
  correct infrastructure for future consumers; it is not yet load-bearing.

**Topic id disambiguation (sprint step 10) was deferred**, not implemented:
ACA-305C section 6 scoped this fix as required *before* `complete`/
`abandon` transitions are unlocked, because the collision it addresses
(`mission:{type}` id reused by a new same-type mission after a prior one
reached a terminal topic status) can only occur once something actually
drives a mission-backed topic to `COMPLETED`/`ABANDONED`. Because no
proposal emitter in this implementation ever requests `complete` or
`abandon` (the only wired transition types are `maintain`, `suspend`, and
`resume`), that terminal state is never reached, and the collision this
fix addresses is not reachable through any path in the current code. The
gate logic in `MissionManager` (section 2.4) fully supports evaluating
`complete`/`abandon` proposals correctly whenever a future emitter
produces them -- but until one exists, implementing the id-disambiguation
fix would be unverifiable dead code. It remains a named, tracked
prerequisite for whichever future sprint wires a `complete`/`abandon`
emitter (most plausibly the `abandonment_criteria` evaluator this section
also deferred).

## 6. Writer/Authority Audit (Sprint Step 13)

Performed by exhaustive grep of `.evolve(` calls carrying `active_mission`
across `aca_os/`, cross-checked against every `active_mission\s*=` match in
the package:

- **`CognitiveState.active_mission` has exactly one writer:**
  `MissionManager` (`mission_manager.py`, five call sites: two
  `MISSION_CREATE` paths, `MISSION_TRANSITION`,
  `MISSION_LOAD_FROM_CONVERSATION_STATE`, `MISSION_UPDATE`). No other file
  calls `.evolve(...)` with `active_mission` in its payload.
- **No double decision:** `evaluate_mission_transition_proposals` returns
  exactly one decision per invocation; `MissionManager.before_kernel`
  calls it exactly once per turn, inside the single `if current.
  active_mission:` branch. Confirmed by construction, not merely by
  absence of a counterexample.
- **No transition without evidence:** every accepted decision traces to a
  specific accepted proposal (`winning_proposal_id`), itself traceable to
  either `_advance_mission`'s fact/slot computation or a topic-navigation
  event with the triggering conversational act attached
  (`evidence.act`). The one exception -- the zero-proposal "accepted no-op
  maintain" case -- produces `mission_after == mission_before` by
  construction, i.e. it is evidence-free *and* effect-free together, never
  evidence-free with an effect.
- **No incoherent topic resume:** fixture 6 is the direct regression test
  for this; it passes. This guarantee is scoped to the `TOPIC_SHIFT`-
  triggered suspend/resume path implemented in section 2.6 -- it does not
  cover every conceivable way `topic_stack` could change (e.g. the
  `CONTINUATION`-triggered resume branch in `update_topic_stack` shares the
  same proposal-emission hook and was not separately fixture-tested here).
- **No internal artifact exposed in visible output:** `mission_decision`,
  `mission_transition_proposals`, and `topic_effect` are all facts/derived-
  state keys, never response text; `NarrativeResponseComposer`/
  `LLMVerbalizer` were not modified and do not read these new keys.

## 7. Byte-Identical Verification

- Fixture 5 (the designated golden-baseline fixture) passes both before and
  after every change in this sprint.
- The full test suite's 730 pre-existing tests all pass, unchanged, after
  every code change in this sprint, verified across three full-suite runs
  (baseline, mid-sprint after the `MissionManager` gate landed, and final
  after the `session.py` fix). Many of these exercise multi-turn
  `auto_claim_guidance` conversations end-to-end through
  `sdk.factory.build_galicia_runtime`, which is the same path this
  sprint's fixtures use -- this is the practical, executed form of
  ACA-305C section 10's byte-identical comparison strategy for this
  sprint's actual scope (Stage 1 plus the `TOPIC_SHIFT` wiring), not a
  separate offline snapshot-diff tool (which ACA-305C section 10 itself
  scoped as a *possible* future artifact, not a requirement for this
  sprint).

## 8. What Closing This Sprint Requires

This document does not propose which of the following to do -- that is an
authority/scope decision for the user, not one to make unilaterally given
the tension identified in section 4:

1. **A decision on fixtures 1-3's dependency on `resolve_pending_slot_
   answers`.** Either: (a) accept that fixtures 1-3 require detection-
   quality work and explicitly move them out of this sprint's acceptance
   criteria into the already-planned ACA-100 Semantic Firewall track, or
   (b) explicitly authorize a narrow, evidenced fix to
   `_contextual_slot_match`'s matching precision as in-scope for a
   follow-up sprint, with its own shadow/benchmark discipline.
2. **A decision on fixture 4 / `abandonment_criteria`.** Same shape of
   choice: defer to detection-quality work, or explicitly scope a narrow
   evaluator (e.g., corroborated by `intent_match` fallback + low act
   confidence, both already-computed signals, rather than new semantic
   classification) as a bounded follow-up.
3. Once (1)/(2) are decided and any resulting work lands, re-run all six
   fixtures and the full suite; only then does this sprint meet its own
   closing conditions.
4. Independently of (1)-(2): if a future sprint wires any `complete`/
   `abandon` emitter, implement the topic id disambiguation fix (section 5)
   before that emitter is allowed to run against real conversations.

## 9. Explicitly Out of Scope (Unchanged From ACA-305C)

Detection-quality improvements to topic-shift/relevance recognition
(ACA-304 Option 2), `ConversationState` restructuring, widening
`SemanticAuthority`'s promotion gate, promoting Candidate Work/Operational
Governance from Shadow, any LLM-verbalization authority role, and the exact
topic-id disambiguation format all remain out of scope for the reasons
already established in ACA-304/305A/305B/305C. Nothing in this
implementation pass reopened any of them.

## 10. Closure: RC1/RC2/RC3 and the Final Closing Implementation

This section covers everything since section 9 was written: three focused
audits (ACA-305D-RC1, RC2 as an implementation pass, RC3) and one final
closing implementation pass, all working exclusively on the concrete debts
sections 4-5 above already identified. No new audit documents or ADRs were
opened during the closing pass itself, per its own instruction.

### 10.1 ACA-305D-RC1 -- Pending Slot Resolution Boundary Audit

Audit only (`docs/architecture/ACA-305D-RC1_Pending_Slot_Resolution_Boundary_Audit.md`).
Root-caused fixtures 1-3 to `resolve_pending_slot_answers`/`_looks_like_
pending_answer` sharing one matching function (`_contextual_slot_match`)
with no confidence floor for its generic fallback (`_match_generic_slot`,
always exactly 0.5 confidence, no relevance check). Left the scope decision
(is this ACA-305D's problem) explicitly open for the user.

### 10.2 Scope decision and ACA-305D-RC2 implementation

The user closed RC1's open scope question explicitly: this is authority/
evidence-control work (the same problem ACA-305 has addressed since
ACA-305A -- low-quality evidence becoming persistent state without an
acceptance criterion), not detection-quality work. Implemented:

- `GENERIC_SLOT_MATCH_CONFIDENCE_FLOOR = 0.6` gates `_match_generic_slot`'s
  output at its one shared root, consulted by both `_looks_like_pending_
  answer` and `resolve_pending_slot_answers` (`_clears_generic_slot_
  confidence_floor`).
- Below-floor matches are recorded explicitly (never silently dropped) and
  converted into an inert `maintain` proposal (empty `mission_delta`) fed
  into the existing `mission_transition_proposals` mechanism.
- Result: fixture 2 passed; fixtures 1 and 3 still failed on response text,
  fixture 4 unaffected (different root cause).

### 10.3 ACA-305D-RC3 -- Reformulation Mechanism Audit

Audit only (`docs/architecture/ACA-305D-RC3_Reformulation_Mechanism_Audit.md`).
Traced why fixtures 1/3's response text stayed red after RC2: `_mission_
conversation_steps`'s `general_orientation` branch hardcoded its one step's
status as `"pending"` (never computed from real slot state, unlike
`auto_claim_guidance`'s branch), so the plan never advances and `_should_
reformulate_selected_question`'s "same slot as last turn" trigger fires
every turn regardless of RC2. Separately, `_reformulated_question_for_slot`
dispatched purely on slot name, never on `mission.type` -- its `user_need`
branch returned hardcoded Galicia-insurance vocabulary for any mission
reaching that generic step. Verdict: a historical, deliberate UX decision
(avoid literal repetition) that had become an incomplete conversational
authority once measured against what ACA-305A-D established. Recommended a
two-edit fix, entirely inside `ConversationState`'s existing ownership, no
new authority.

### 10.4 Closing implementation

The user authorized closure directly, with explicit constraints: fix
`_reformulated_question_for_slot` definitively; resolve repetition **only**
where it contradicts the approved contract (do not eliminate useful
reformulations; only stop a question reappearing when there is sufficient
evidence `MissionManager` decided *another* transition); keep everything
else -- single writer, proposal/decision contracts, topic integration,
observability, byte-identical `auto_claim_guidance` -- intact.

**Implemented, in `aca_os/conversation_state.py`:**

1. `_reformulated_question_for_slot` now takes `mission_type`. The four
   `auto_claim_guidance`-specific branches (`injuries`, `user_role`,
   `claim_report_loaded`, `documentation_available`) only fire when
   `mission_type == "auto_claim_guidance"` -- byte-identical text for that
   mission, unreachable for any other. `user_need`'s branch no longer
   contains any Galicia/insurance vocabulary; it returns a domain-neutral
   reformulation instead. `_maybe_reformulate_required_question` extracts
   `mission_type` from `conversation_plan["active_plan"]["mission_type"]`,
   already available at the call site -- no new plumbing.
2. `_mission_conversation_steps`'s generic fallback branch now computes
   `"understand_user_need"`'s status via the existing `_step_status_for_
   known_value` helper (the same one `auto_claim_guidance`'s branch already
   uses four times) instead of a hardcoded `"pending"` literal -- RC3's
   first recommended edit, closing the plan-advancement gap for any future
   case where `user_need` genuinely gets answered.
3. A new evidence path in `resolve_pending_slot_answers`, symmetric with
   RC2's rejection path: when **no** matcher (explicit or contextual,
   dedicated or generic) finds any signal at all for a pending question
   (distinct from a low-confidence match -- this is the complete absence of
   one, ACA-305D-RC1 section 7's fixture-4 root cause), it is recorded
   explicitly and converted into an inert `suspend` proposal
   (`_slot_unmatched_mission_proposal`), evaluated by `MissionManager` like
   any other. `suspend`, not `abandon`: a single non-engaging turn does not
   prove the mission was given up on.
4. This new evidence path is **deliberately scoped away from
   `auto_claim_guidance`** (`_MISSION_TYPES_WITH_OWN_RECOVERY_AUTHORITY =
   {"auto_claim_guidance"}`). Reason, found during verification (10.5):
   that mission type already owns a complete, pre-existing, approved
   recovery authority for exactly this situation --
   `conversation_fulfillment.v1` (introduced in the same commit as
   reformulation itself, `c0c2bcf`), which requires the mission to stay
   `in_progress`, mark the unanswered step `failed`, and reask via
   reformulation, not transition. Proposing `suspend` there would have
   contradicted an already-approved contract, not fixed a gap.

**Fixture assertions corrected** (per the closing sprint's explicit
instruction: determine whether a remaining failure is implementation,
incorrect benchmark, or inconsistent contract, and fix directly if it
belongs to ACA-305D):

- **Fixture 3**: originally required `response3 != response2` for "Hola" /
  "¿Cómo estás?" / "Ninguno". Once domain contamination was removed (10.4
  point 1), both turns legitimately produce the *same*, now domain-correct,
  reformulated question -- correct, per this sprint's own explicit rule,
  because no other transition was warranted between them. The original
  assertion contradicted the contract stated in this sprint's instructions.
  Corrected to check what that contract actually cares about: no
  wrong-domain content, no silent absorption of "ninguno" as the confirmed
  `user_need` value.
- **Fixture 4**: originally required the mission to abandon/suspend/replace
  for "¿Dios existe?" against `auto_claim_guidance`. Verification (10.5)
  found this contradicted the pre-existing, approved `conversation_
  fulfillment.v1` contract, which requires the *opposite* (stay
  `in_progress`, reask) for exactly this case. Corrected to verify the
  actually-correct, already-approved behavior: the pre-existing fulfillment
  contract records the failed step and `reask_or_reformulate` recovery, the
  mission stays `auto_claim_guidance`/not suspended, and turn 2's response
  is the reformulated (not verbatim-repeated) injuries question.

### 10.5 A real regression found and fixed during verification

The first version of point 3 above (scoped only by mission type, no other
change) broke `test_conversation_fulfillment.py::test_unanswered_expected_
step_records_failure_and_recovery_action` -- a pre-existing, approved test
for `auto_claim_guidance`, unrelated to ACA-305 until this point.

Root cause, traced precisely rather than guessed: `_conversation_failed_
steps` (`conversation_state.py`, part of the pre-existing `conversation_
fulfillment.v1` contract) treats the mere *presence* of `derived_state
["slot_resolution"]` as "something legitimate happened this turn, do not
mark the expected step failed" (`if conversation_state.derived_state.get(
"slot_resolution") or ...: return []`). The new "unmatched" evidence
(section 10.4 point 3) was, in its first version, written into that same
`slot_resolution` trace even when nothing was actually resolved --
incorrectly tripping this pre-existing guard for `auto_claim_guidance`
regardless of the mission-type scoping in point 4, because the guard fires
on trace presence, not on the proposal that trace happens to feed.

Fixed by separating concerns precisely: `derived_state["slot_resolution"]`
is set *only* when `resolutions` is non-empty -- byte-identical to its
pre-ACA-305D-RC2 meaning. Rejection and unmatched evidence now live under a
new key, `derived_state["slot_resolution_evidence"]`, read only by the new
mission-transition-proposal builders, never by `_conversation_failed_
steps`. This is the smallest change that restores the pre-existing
contract exactly while keeping the new evidence fully observable.

Verified: `test_conversation_fulfillment.py` (all tests, including the
previously-broken one) passes after this fix, alongside all six fixtures.

### 10.6 Final Verification

- **All six ACA-305C fixtures pass.**
- **Full suite: 736 passed, 0 failed** (730 pre-existing tests + 6
  fixtures). Verified across three full-suite runs during this closing
  sprint (one baseline-confirming run after the reformulation/plan-status
  fix landed showing 3 remaining failures as predicted by section 10.4's
  analysis, one showing the `conversation_fulfillment` regression, one
  final fully green run after the section 10.5 fix).
- **Single writer**: re-verified by exhaustive grep of every `.evolve(`
  call in `aca_os/` carrying `active_mission` -- still exactly the five
  call sites inside `MissionManager` (`mission_manager.py`), unchanged by
  this closing sprint. `ConversationState`'s own `active_mission` field
  (a projection, not `CognitiveState`'s authoritative copy) continues to be
  written only via `replace(...)`, never `.evolve(...)`.
- **One transition per turn**: unchanged by construction --
  `evaluate_mission_transition_proposals` still returns exactly one
  decision per invocation, and the two new evidence sources (10.4 points 3
  and RC2's rejection path) feed the same precedence-ordered candidate list
  as every other proposal source (`abandon > replace > complete > suspend >
  resume > maintain`), never bypass it.
- **Observability**: the two new proposal types (`slot_rejection`,
  `slot_unmatched`) use the exact same `MissionTransitionProposal`/
  `MissionTransitionDecision` shapes already exposed via `state.facts
  ["mission_transition_decision"]` and `RuntimeIntrospectionAPI`'s
  `mission_decision` summary -- no changes were needed to `introspection.py`
  or `execution_trace.py` for them to be visible; both were already
  shape-agnostic.
- **Byte-identical `auto_claim_guidance`**: verified twice -- fixture 5
  passes unchanged, and `test_conversation_fulfillment.py`'s full suite
  (the most direct, pre-existing regression test for this mission type's
  behavior) passes, including the specific test that exposed the one real
  regression this sprint found and fixed.

### 10.7 What Remains Genuinely Out of Scope

Unchanged from section 9: detection-quality improvements (ACA-304 Option
2), `ConversationState` restructuring, widening `SemanticAuthority`'s
promotion gate, promoting Candidate Work/Operational Governance from
Shadow, LLM-verbalization authority, and the topic-id disambiguation format
(section 5 -- still deferred, still unreachable, since no `complete`/
`abandon` emitter exists for a mission-backed topic to collide against; the
new `suspend`-on-no-match evidence path does not change this, since
`suspend` was already a reachable transition type before this closing
sprint via the topic-shift path).

### 10.8 Final Closure Validation (Repository Prepared for Commit)

A dedicated closing session re-validated everything from the then-current
working tree, with no code changes required (the tree was already at the
green state; only `HANDOFF.md` and this section were updated):

- Full suite re-run from scratch: **736 passed, 0 failed** (fourth
  consecutive fully-green full-suite run, counting section 10.6's).
- All six permanent fixtures green (included in the run above).
- Domain-contamination sweep re-verified: every remaining Galicia/insurance
  string in `conversation_state.py` is reachable only through
  `auto_claim_guidance`-scoped mechanisms (its own slots, its
  `mission_type`-gated reformulations, its dedicated question builders).
  The `user_need` entries in both slot-to-question dictionaries
  (`_justified_question_for_slot`, `_question_for_missing_information`)
  and in `_reformulated_question_for_slot` are domain-neutral.
- Single-writer audit re-verified: every `.evolve(...)` carrying
  `active_mission` lives in `mission_manager.py` (five call sites, all
  `MissionManager`).
- One-transition-per-turn re-verified: `evaluate_mission_transition_
  proposals` has exactly one call site (`MissionManager.before_kernel`).
- Observability validated: `mission_transition_decision` exposed via
  `state.facts`, `RuntimeIntrospectionAPI`'s `mission_decision` summary,
  and `MISSION_TRANSITION`/`MISSION_LOAD_FROM_CONVERSATION_STATE`
  attribution in Execution Trace.
- No public API was modified; no compatibility was broken (zero
  pre-existing-test regressions across every run in the series).
- `CURRENT_STATE.md` and `HANDOFF.md` updated to reflect closure. No
  commit, no push -- the repository is left fully prepared for the final
  ACA-305 commit, which requires explicit user instruction.

**ACA-305D is closed.** ACA-305 (A through D, RC1-RC3) is complete.
