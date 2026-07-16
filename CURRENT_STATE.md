# ACA Framework — Current State

**Last updated:** 2026-07-16  
**Status:** Active development  
**Source of truth priority:** running code → tests/benchmarks → architecture documents → this handoff

## Current position

ACA has a stable deterministic Runtime, a growing cognitive/conversational layer, complete turn-level observability, and an external web demo. The project is now transitioning from architecture-first development toward controlled real-world conversational testing. **The ACA-305 series (A through D, plus RC1-RC3) is complete.** The Mission Lifecycle Authority question raised by ACA-304 now has a closed architecture decision (ACA-305A), a closed conceptual contract design (ACA-305B), a closed mission/topic integration decision with permanent fixtures (ACA-305C), and a **closed, fully verified implementation (ACA-305D)** — all six ACA-305C fixtures pass, the full test suite is green (736/736), and every invariant (single writer, one transition per turn, observability, byte-identical `auto_claim_guidance`) is verified. The working tree is uncommitted and ready for review/commit; no commit or push was made per instruction.

## Latest completed work

### ACA-305 — Final closure validation (dedicated closing session)

A dedicated closing session re-validated the finished state with no code changes needed: full suite re-run from scratch (**736 passed, 0 failed** — fourth consecutive fully-green run), all six fixtures green, domain-contamination sweep clean (every remaining insurance string in `conversation_state.py` is reachable only through `auto_claim_guidance`-scoped mechanisms; `user_need` is domain-neutral everywhere), single-writer and one-transition-per-turn invariants re-verified by exhaustive grep, observability confirmed. `HANDOFF.md` updated (its "current next step" still pointed at the pre-ACA-305A state). Repository left fully prepared for the final ACA-305 commit; no commit or push made, per instruction. See `docs/architecture/ACA-305D_Mission_Lifecycle_Minimal_Controlled_Implementation.md` §10.8.

### ACA-305D — CLOSED (all fixtures green, full suite green, all invariants verified)

Closing this sprint required three further audits/passes beyond the original ACA-305D implementation (all summarized below, in reverse chronological order), each working only on debts the prior one identified, per explicit user instruction not to open new audits or ADRs during closing.

**Final closing implementation** (this pass): with scope for the RC1 finding explicitly authorized by the user (this is authority/evidence-control work, the same category ACA-305 has addressed since ACA-305A — not detection-quality work), implemented:

1. **`_reformulated_question_for_slot` corrected definitively.** Now takes `mission_type`; the four `auto_claim_guidance`-specific branches only fire for that mission type (byte-identical text, unchanged); `user_need`'s branch no longer contains any Galicia-insurance vocabulary — replaced with a domain-neutral reformulation. `user_need` has belonged conceptually to `general_orientation` since the project's bootstrap commit (`da71b6e`, 2026-07-03); the insurance vocabulary was traced to a later, separate commit (`c0c2bcf`, 2026-07-12) that introduced reformulation for a benchmark that never exercised `general_orientation` — an accidental cross-domain leak, not a deliberate design choice.
2. **`_mission_conversation_steps`'s `general_orientation` branch** now computes its step's status via the existing `_step_status_for_known_value` helper instead of a hardcoded `"pending"` literal (RC3's finding: the plan could never advance for this mission type, independent of anything else).
3. **A new `suspend` evidence path** in `resolve_pending_slot_answers`, symmetric with RC2's rejection path: when no matcher finds any signal at all for a pending question (distinct from a low-confidence match), it's recorded explicitly and proposed to `MissionManager` as `suspend` (not `abandon` — a single non-engaging turn doesn't prove abandonment). **Deliberately scoped away from `auto_claim_guidance`**, which already owns a complete, pre-existing, approved recovery authority for this exact situation (`conversation_fulfillment.v1`, introduced in the same commit as reformulation itself) that requires reask-via-reformulation, not a mission transition — proposing `suspend` there would have contradicted an already-approved contract.
4. **A real regression found and fixed during verification**: the first version of point 3 broke `test_conversation_fulfillment.py::test_unanswered_expected_step_records_failure_and_recovery_action` — not because of the mission-type scoping (which was already correct) but because the new evidence was, in its first version, written into `derived_state["slot_resolution"]`, whose mere *presence* a pre-existing, unrelated mechanism (`_conversation_failed_steps`) treats as "something legitimate happened, don't mark failed." Fixed by moving rejection/unmatched evidence to a new, separate key (`derived_state["slot_resolution_evidence"]`), restoring the pre-existing contract's exact original meaning.
5. **Two fixture assertions corrected**, per this sprint's explicit instruction to determine whether a remaining failure is implementation, incorrect benchmark, or inconsistent contract, and fix directly if it belongs to ACA-305D: fixture 3 no longer requires `response3 != response2` (repeating the *same*, now domain-correct question when no other transition is warranted is contractually correct per this sprint's own rule); fixture 4 no longer requires an abandon/suspend/replace transition (the pre-existing, approved `conversation_fulfillment` contract's reask-based recovery is the actually-correct behavior for `auto_claim_guidance`, discovered via the regression in point 4).

**Final verification**: all six ACA-305C fixtures pass. **Full suite: 736 passed, 0 failed** (730 pre-existing + 6 fixtures), verified across three full-suite runs this closing sprint. Single-writer audit re-verified (still exactly five `.evolve(..., active_mission=...)` call sites, all in `MissionManager`). One-transition-per-turn holds by construction (both new evidence sources feed the same precedence-ordered candidate list as every other proposal). Observability required no changes (new proposal types reuse the existing `MissionTransitionProposal`/`MissionTransitionDecision` shapes, already exposed via Introspection/Execution Trace). Byte-identical `auto_claim_guidance` verified twice (fixture 5, plus the full `test_conversation_fulfillment.py` suite that exposed and confirmed the fix for the one regression found).

Full detail: `docs/architecture/ACA-305D_Mission_Lifecycle_Minimal_Controlled_Implementation.md` §10.

**Prior passes this sprint built on** (each already summarized in its own entry below, kept for the historical record): ACA-305D-RC1 (audit, found the shared root cause), ACA-305D-RC2 (implemented the confidence gate, flipped fixture 2 green), ACA-305D-RC3 (audit, found the reformulation/plan-advancement gap that RC2 alone couldn't fix).

### ACA-305D-RC3 — Reformulation Mechanism Audit (audit only, no code changed)

- Determined why fixtures 1 and 3's response text stayed red even after ACA-305D-RC2 correctly stopped slot-value absorption: **the reformulation mechanism never advances past its first step for `general_orientation`**, independent of anything RC2 touched.
- **Root finding**: `_mission_conversation_steps`'s generic fallback branch (`conversation_state.py:~1853-1865`, used by `general_orientation` and any future mission type not special-cased) hardcodes its one step's status as `"pending"` literally — never computed from the slot's actual state, unlike `auto_claim_guidance`'s branch which correctly uses `_step_status_for_known_value`. This means `_current_conversation_step` selects the same step every turn forever, so `_should_reformulate_selected_question`'s "same slot as last turn" trigger (`conversation_state.py:~2397-2414`) fires regardless of whether the prior answer was accepted, rejected, or never given a chance.
- **Second finding**: `_reformulated_question_for_slot` (`conversation_state.py:~2417-2437`) dispatches purely on slot name, never reads `mission.type` — its `user_need` branch returns a hardcoded insurance-claim-specific string for *any* mission type reaching the generic fallback step. Confirmed this also fires for `auto_claim_guidance`'s `injuries` slot in fixture 4's turn 2 (a different hardcoded string), though fixture 4's assertions don't check response text.
- Verdict on the sprint's central question: **historical, deliberate UX decision** (avoid literally repeating a question — corroborated by `evaluation.py`'s `_count_reformulated_questions`, an existing benchmark metric treating reformulation as a tracked feature, not an accident) **that has become an incomplete conversational authority**: it consults none of `resolve_pending_slot_answers`'s result, `MissionTransitionDecision`, explicit rejection evidence, or mission-change proposals — confirmed by exhaustive code inspection, not just fixture behavior.
- Neither function consults `mission.type`, `slots[slot].status`, or any ACA-305D-RC2 evidence (`slot_resolution.rejections`) — confirmed these are structurally absent from every parameter these functions receive.
- **Architectural recommendation**: reformulation should depend on *both* slot status (fix the hardcoded `"pending"`, reusing the already-proven `_step_status_for_known_value` pattern) *and* mission-type-aware content (scope `_reformulated_question_for_slot`'s hardcoded wording to the mission domain it assumes, falling back to the existing un-reformulated question otherwise) — both inside `ConversationState`'s existing planning-layer ownership, no new component, no new authority.
- **Open call flagged, not resolved**: even with both fixes, fixture 3 might still show the *same* (now domain-correct) question repeated across turns 2-3, since the plan-advancement gap doesn't itself stop repetition — only wrong-domain content. Whether that residual repetition should still count as a fixture-3 failure is left as an explicit decision before implementation.
- Full call graph, per-question evidence (14 questions answered), and the minimal two-edit closing proposal: `docs/architecture/ACA-305D-RC3_Reformulation_Mechanism_Audit.md`.
- No code, test, or contract was modified.

### ACA-305D-RC2 — Generic Slot Match Confidence Gate (implemented, verified, ACA-305D still not closed)

- Scope decision made explicitly by the user, closing ACA-305D-RC1 §10's open question: the `resolve_pending_slot_answers` fix is authority/evidence-control work (part of the ACA-305 series since ACA-305A), not detection-quality work — no lexical whitelist expansion, no `SemanticAuthority` change, no NLP.
- Implemented (`aca_os/conversation_state.py`): `GENERIC_SLOT_MATCH_CONFIDENCE_FLOOR = 0.6` gates `_match_generic_slot`'s output (always exactly 0.5 confidence, no relevance check — ACA-305D-RC1 §5) at its one shared root (`_clears_generic_slot_confidence_floor`, consulted by both `_looks_like_pending_answer` and `resolve_pending_slot_answers`, per RC1 §8's "one function, one fix" finding). `injuries`/`user_role` matching (dedicated term-list matchers) is untouched.
- Below-floor matches are no longer silently absorbed *or* silently discarded: they are recorded explicitly in `derived_state["slot_resolution"].rejections`, and converted into an inert `MissionTransitionProposal` (`_slot_rejection_mission_proposal`, `transition_type="maintain"`, empty `mission_delta` — requests no change, purely makes the rejection auditable) fed into the same `mission_transition_proposals` mechanism ACA-305D built. `MissionManager` remains the sole decider; `resolve_pending_slot_answers` proposes, never decides.
- Pre-implementation invariant check against ACA-305B §8 and ACA-305C §7: no violations found. Single writer holds (`resolve_pending_slot_answers` only ever calls `ConversationState`'s own `replace(...)`, never `CognitiveState.evolve(...)`); proposal carries no `mission_after`; decision traceable and idempotent (verified: `mission_before == mission_after` for the no-op case).
- **Verified, empirically**: `"Mis vacaciones"` is no longer absorbed as the `user_need` slot's value (confirmed via direct diagnostic — slot stays unset rather than holding the raw message text), and the rejection produces a correctly-shaped, accepted, no-op `MissionTransitionDecision` trace.
- **Full suite: 733 passed, 3 failed (736 total).** Zero regressions across all 730 pre-existing tests. **Fixture 2 now passes** (was red). Fixtures 5 and 6 remain green. Fixtures 1, 3, 4 remain red.
- **Important finding, not a contract violation**: fixtures 1 and 3's *response text* assertions still fail — but not because the absorption fix didn't work (verified above that it did). The repeated "el arreglo, la denuncia, la documentación o los tiempos" text is produced by a separate, independent mechanism — `_reformulated_question_for_slot` (`conversation_state.py:~2344-2364`, a hardcoded string for `slot == "user_need"` regardless of mission type) triggered by `_should_reformulate_selected_question` (`conversation_state.py:~2324-2341`, fires whenever the *same slot* was also the previous turn's plan step — a pure repetition check, independent of whether the previous "answer" was accepted or rejected). This mechanism runs in response planning and is untouched by, and unaffected by, the confidence-gate fix. Fixture 4 is unaffected as expected (its root cause — no `abandonment_criteria` evaluator — was never addressed by this fix; RC1 already established it needed a different mechanism).
- No taxonomy beyond what existed was introduced (no new `SlotStatus`/`TopicStatus` value); rejection is recorded as trace/proposal data only, per the user's "no full taxonomy unless strictly necessary" instruction.
- ACA-305D remains **not closed**: fixtures 1, 3, 4 still fail, so per ACA-305D's own closing conditions this cannot be declared complete. The next decision needed is whether to also address `_reformulated_question_for_slot`'s hardcoded vocabulary / `_should_reformulate_selected_question`'s repetition trigger (a separate, narrow, unauthorized-so-far mechanism) and whether/how to give fixture 4 its `abandonment_criteria` evidence path (per ACA-305D-RC1's still-open recommendation).

### ACA-305D-RC1 — Pending Slot Resolution Boundary Audit (audit only, no code changed)

- Exhaustively audited `resolve_pending_slot_answers` (`conversation_state.py:941-1016`) and its callers/inputs/authorities, per ACA-305D's own finding that this function — not anything in ACA-305D's implementation — is the root cause of fixtures 1-3 remaining red.
- **Key finding**: `_looks_like_pending_answer` (`conversation_state.py:6014-6025`, used during act *recognition*, before slot resolution even runs) calls the exact same `_explicit_slot_matches`/`_contextual_slot_match` functions that `resolve_pending_slot_answers` later calls to perform the actual absorption. This is **one shared root cause**, not two — a fix to the matching function's permissiveness propagates correctly to both the act-candidacy decision and the slot-write decision, because there is only one implementation.
- **Key finding**: `_match_generic_slot` (`conversation_state.py:6351-6362`, the matcher for any slot besides `injuries`/`user_role` — today, only `general_orientation`'s `user_need`) has no relevance check at all: any message ≥2 characters, not in an 8-phrase "uncertain" whitelist, is accepted as a valid answer at a flat confidence of 0.5 — and **that confidence is never gated by anything downstream**. The field is computed and discarded, the same category of gap `semantic_authority_pilot.py`/ACA-305D's own `MINIMUM_CONFIDENCE` table already close elsewhere in this codebase, just never extended to this layer.
- **Key finding**: fixture 4 ("¿Dios existe?" against `auto_claim_guidance`) has a *different* root cause than fixtures 1-3. `_match_injuries` correctly returns `None` for it (no generic fallback exists for `injuries`/`user_role`) — the failure there is the *absence of any record or consumer* for a rejected match, not over-absorption.
- **Key finding**: `_act_suppresses_slot_resolution` (`conversation_state.py:4263-4273`) already correctly defers to `TOPIC_SHIFT` when that act is recognized — the suppression mechanism is sound; it simply never fires for these four messages because `_mentions_topic_shift`'s lexical detector never recognizes them as topic-shift candidates in the first place, so `PENDING_ANSWER` wins uncontested (not because of priority ordering — act selection sorts confidence-first, priority only as a tiebreaker, `conversation_state.py:4230-4251` — priority is not actually the mechanism here).
- Regression-risk check: no test found that exercises or depends on `_match_generic_slot`'s permissiveness; the one relevant existing test (`test_slot_lifecycle.py::test_contextual_yes_resolves_user_role_after_pending_question`) exercises `_match_user_role`'s dedicated branch, unaffected by any fix scoped to the generic matcher.
- Recommended minimal fix shape (not implemented): a confidence floor on generic contextual slot matches, with rejected/absent matches routed as new evidence into the `mission_transition_proposals` mechanism ACA-305D already built — no change to `SemanticAuthority`, lexical whitelists, or any detection logic required.
- **Explicit open scope decision, not resolved by this audit**: `resolve_pending_slot_answers`/`_looks_like_pending_answer` were never named as in-scope by ACA-305A/B/C. Whether the minimal fix belongs to ACA-305D, a separate sprint, or requires an ACA-305C amendment is left for explicit user decision — see `docs/architecture/ACA-305D-RC1_Pending_Slot_Resolution_Boundary_Audit.md` §10.
- Full flow trace, ownership analysis, classification matrix, and per-message causal breakdown: `docs/architecture/ACA-305D-RC1_Pending_Slot_Resolution_Boundary_Audit.md`.
- No code, test, or contract was modified. ACA-305D's existing implementation was not touched or reverted.

### ACA-305D — Mission Lifecycle Minimal Controlled Implementation (original pass — superseded, see "ACA-305D — CLOSED" above)

- Implemented and landed in the working tree (uncommitted): the `SWITCH_TOPIC` semantics correction, `MissionTransitionProposal`/`MissionTransitionDecision` contracts, `MissionManager` as sole evaluator/writer (replacing the equality-check adoption ACA-305A found), `_advance_mission` migrated to a proposal emitter with verified byte-identical output, mission↔`topic_stack` suspend/resume integration, and Introspection/Execution Trace observability for every mission decision.
- Verification: full suite run three times across the sprint. Final result **732 passed, 4 failed** (736 total = 730 pre-existing + 6 new ACA-305C fixtures). **All 730 pre-existing tests pass — zero regressions.** 2 of 6 new fixtures pass (fixture 5, byte-identical baseline; fixture 6, topic-change-and-return coherence — this is the direct regression test proving topic resume now correctly resumes the mission, closing ACA-305C's core finding). Fixtures 1, 2, 3, 4 remain red.
- A real regression was found and fixed mid-sprint: `ExecutionSession.compare` (`aca_os/session.py`) hardcoded `MISSION_LOAD_FROM_CONVERSATION_STATE` as canonically equivalent to `MISSION_CREATE` for session-stability comparisons; the new `MISSION_TRANSITION` operation broke that equivalence until added to the same rule. Documents that "run tests after each block" caught a real issue, not just a formality.
- **Why fixtures 1/2/3 remain red**: root-caused (not guessed) to `resolve_pending_slot_answers` (`conversation_state.py:941-1016`) — a mission-content-writing site upstream of every proposal-emission point this sprint added, that absorbs low-specificity messages as pending-slot answers via `_contextual_slot_match`. Fixing this is detection-quality work (ACA-304 Option 2), which ACA-304/305B/305C all independently scoped OUT of the mission-authority track this sprint implements, and which this sprint's own rules ("no cambies arquitectura fuera del alcance") caution against touching without its own shadow/benchmark discipline. **Why fixture 4 remains red**: requires evaluating `abandonment_criteria`, which needs the same out-of-scope relevance judgment.
- This is a genuine, unresolved tension between this sprint's unconditional acceptance criteria and the explicit out-of-scope boundaries set by the three prior sprints in this same series — surfaced explicitly rather than resolved unilaterally in either direction (see `docs/architecture/ACA-305D_Mission_Lifecycle_Minimal_Controlled_Implementation.md` section 8 for the two decision options this leaves open).
- Deferred, not silently dropped: topic id disambiguation (`mission:{type}` collision) — confirmed unreachable in this implementation since no emitter yet proposes `complete`/`abandon`; tracked as a named prerequisite for whichever future work wires one.
- Full implementation detail, regression evidence, and the exact decision needed to close this sprint: `docs/architecture/ACA-305D_Mission_Lifecycle_Minimal_Controlled_Implementation.md`.
- **Per this sprint's own instructions, ACA-305D is NOT declared closed**: not all fixtures pass, so this section must not be read as sprint completion — it is an accurate progress record.

### ACA-305C — Mission Lifecycle Benchmark and Integration Closure

- Audited `topic_stack`'s own machinery with the same rigor previously applied to `active_mission` (ACA-305A/B), since no prior sprint had done so.
- Key finding: a mission-backed topic-stack entry (`id = "mission:{type}"`) is a **live projection of the mission**, recomputed every turn by `_topic_from_current_state`/`_topic_refreshed_from_state` (`conversation_state.py:4506-4583`) — not an independently authored record. `topic_stack` is the broader structure; it also holds `unresolved_topic`/`focus` entries outside mission status.
- Key finding: `TopicStatus.COMPLETED` and `TopicStatus.ABANDONED` (`conversation_state.py:216-245`) are, exactly like `MissionLifecycleStatus.COMPLETED`/`SUSPENDED` (ACA-305A §4.4), fully declared, legally reachable in `TOPIC_LIFECYCLE`, and never assigned anywhere in the codebase. This document's mission↔topic mapping reuses these two dormant states rather than inventing new ones.
- Key finding: today, resuming a topic **does not** resume its mission — `_topic_refreshed_from_state` only re-syncs facts/slots when the resumed topic's `mission_type` already matches the currently active mission; when it doesn't, `active_mission` is left untouched, producing a real, evidenced divergence between what `topic_stack` shows as active and what `MissionManager` believes the mission is.
- Key finding, required correction (not just new wiring): `_mission_impact_for` (`conversation_state.py:4366-4381`) currently puts `SWITCH_TOPIC` in `preserve_active_mission`'s set and **excludes** it from `may_change_mission_state`'s set — the opposite of this integration's decision. ACA-305D must fix this one-line set membership before wiring `TOPIC_SHIFT`-sourced mission proposals, or ACA-305B §14's own eligibility filter silently blocks them.
- Key finding: the topic-id scheme (`mission:{type}`, one slot per type) would collide if a same-type mission is created after its topic reached a terminal (`COMPLETED`/`ABANDONED`) status — flagged as a required, narrowly-scoped fix (exact format left to ACA-305D), not left ambiguous.
- Decision: mission is a specialization of topic (same conceptual unit for mission-backed entries); ownership stays split exactly as already declared (`MissionManager` owns `active_mission`, `ConversationState` owns `topic_stack`); a full forward (mission transition → topic effect) and reverse (topic navigation → mission proposal) cross-transition matrix was defined, reusing existing mechanisms (e.g. `replace` reuses the existing `TOPIC_SHIFT`/`new_topic` suspend behavior) wherever possible.
- Six permanent fixtures fully specified (greeting/social-question, general-mission natural topic change, explicit rejection, completely unrelated question, byte-identical `auto_claim_guidance` continuation, topic change and return), each with expected proposal/decision/transition/topic effect/observable response/audit info/prohibited behavior.
- Byte-identical comparison strategy defined: baseline capture → decision-relevant vs. additive/observability field classification → regression rule for Stage 1 → expected divergence scoped to specific fixtures from Stage 2/3 onward.
- Full evidence, integration decision, cross-transition matrix, invariants, fixtures, risks and the exact ACA-305D implementation plan: `docs/architecture/ACA-305C_Mission_Lifecycle_Benchmark_and_Integration_Closure.md`.
- No code, class, contract, or test was written or modified.

### ACA-305B — Mission Lifecycle Contracts and Invariants

- Designed the complete conceptual contract for `MissionManager` to evaluate proposed mission transitions (`maintain`, `complete`, `suspend`, `resume`, `replace`, `abandon`) and apply exactly one atomic transition per turn, per ACA-305A's decision.
- Re-verified ACA-305A's evidence against current code before designing (no repository changes had occurred between the two sprints).
- The state machine and valid-transition table reuse the existing `MissionLifecycleStatus`/`MISSION_LIFECYCLE` table (`conversation_state.py:65-122`) unchanged — `complete`/`suspend`/`resume` map onto edges that table already legally declares but that no code today ever computes (ACA-305A §4.4); `replace`/`abandon` are new, table-independent, terminal-or-restart transitions.
- Closed the specific anti-pattern ACA-305A found (`_advance_mission`'s output adopted by `MissionManager` via bare equality check, `mission_manager.py:17-21`): proposals may never carry a final `active_mission`/`mission_after`/`lifecycle_status` value; only `MissionManager` computes the result, from a `mission_delta` + `transition_type` + evidence.
- Defined an explicit emitter allowlist and exclusion list (`ConversationState`, gated `SemanticAuthority` evidence in; `NarrativeResponseComposer`/`LLMVerbalizer`/`operational_work_mapper`/tools/plugins out) and a 4-stage migration (shadow → single-path gated cutover for the already-working `auto_claim_guidance` case → extend coverage to `general_orientation` + wire `TOPIC_SHIFT`/`abandonment_criteria`/`mission_impact.may_change_mission_state` → unlock terminal/lateral transitions), mirroring ACA-019's phased-migration pattern and the existing `semantic_authority_pilot.py` gated-selector shape.
- Two implementation-detail questions were deliberately left open (not authority questions): whether `_advance_mission`'s computation physically moves into `MissionManager` or stays called from `ConversationState`; how a mission-level `replace`/`abandon` reconciles with `topic_stack`'s own independent suspend/resume semantics. Both are explicitly scoped to ACA-305C.
- Full contract, state machine, invariants, ownership/idempotency/audit rules, edge cases, risks and ACA-305C acceptance criteria: `docs/architecture/ACA-305B_Mission_Lifecycle_Contracts_and_Invariants.md`.
- No code, class, contract, or test was written or modified.

### ACA-305A — Mission Lifecycle Authority Architecture Decision

- Audited, with fresh code evidence (not a re-read of ACA-304), who may create, advance, complete, suspend, replace or abandon `active_mission`.
- Correction to ACA-304: `MissionManager.before_kernel` (`aca_os/mission_manager.py:15-27`) has a second branch ACA-304 did not quote. For `auto_claim_guidance` missions, `ConversationState._advance_mission` (`aca_os/conversation_state.py:5483-5530`) already computes a real 7-state lifecycle machine every turn, and `MissionManager` adopts it unconditionally via an equality check — not evaluated, not gated. This path never fires for `general_orientation` (the type in ACA-304's reproduced failure).
- New finding: `MissionLifecycleStatus.COMPLETED`/`SUSPENDED` (`conversation_state.py:86-122`) are legal transition targets that no code ever actually computes (`_mission_status_for`, `conversation_state.py:5533-5542`, has only four possible outputs, neither of these two) — a mission can never actually finish or pause in the live system today.
- New finding: a fourth write-only mission-relevant signal, `mission_impact.may_change_mission_state` / `preserve_active_mission` (`conversation_state.py:4366-4381`), joins ACA-304's three (`TOPIC_SHIFT`, `impact.mission_reevaluation`, `abandonment_criteria`) — computed, never consumed.
- Confirmed via exhaustive writer audit (15 files matched `active_mission`): the single-writer invariant on `CognitiveState.active_mission` itself holds (`MissionManager` is the only `.evolve(...)` call site). What does not fully hold is the single-*decision*-authority intent already declared in `conversation_state.py:702-711` and `authority_dependency_graph.py:263` — `ConversationState._advance_mission` is a de facto second, ungated decision site for one mission type.
- Decision: `MissionManager` remains the sole writer of `active_mission` (no second writer, no second planner). It gains a single new responsibility — evaluating proposed transitions from any component (fact/slot advancement, topic-shift, abandonment criteria) and atomically accepting or rejecting them with a logged, traceable reason — generalizing two shapes that already exist in this codebase (`_advance_mission`'s trace dict and `semantic_authority_pilot.py`'s gated-selection pattern) rather than inventing new machinery.
- Full evidence, alternatives, risks, invariants and the recommended decision: `docs/architecture/ACA-305_Mission_Lifecycle_Authority_ADR.md`.
- No code, class, or contract was written. No tests affected (audit only).

### ACA-303 — Observability Completeness

- Component Registry expanded from 17 to 36 official components.
- SemanticAuthority, SemanticProjector, authority selectors, RuntimeExecutor, LegacyRuntimeExecutor, eight step handlers, Kernel, Compiler, MissionManager, NarrativeResponseComposer and LLMVerbalizer are now observable.
- ConversationalGoal authority metadata was corrected to match runtime behavior.
- Runtime introspection now exposes `output_decision`, including Composer, Conversational-First and LLM verbalization decisions.
- Registry, Authority Dependency Graph and Runtime Introspection were verified against the same official system.
- Verification result: **730/730 tests passed**.
- Existing benchmarks and visible smoke responses remained unchanged.

### Real-world conversational finding

The following conversation was reproduced against the real Runtime:

```text
Usuario: Hola
ACA: Hola. Contame qué necesitás y te oriento.

Usuario: ¿Cómo estás?
ACA: ¿Qué punto querés resolver primero: el arreglo, la denuncia, la documentación o los tiempos?

Usuario: Mis vacaciones
ACA: [repite la misma pregunta]

Usuario: Ninguno
ACA: [repite la misma pregunta]

Usuario: ¿Dios existe?
ACA: [repite la misma pregunta]
```

The investigation found:

- `MissionManager.before_kernel()` creates the mission once and does not reevaluate whether it remains relevant.
- No official component currently owns authority to organically change, finish or abandon an active mission.
- ACA already computes topic-shift-related signals (`TOPIC_SHIFT`, `mission_reevaluation`, `abandonment_criteria`), but none is connected to mission authority.
- Natural topic-shift detection is currently too lexical and narrow.
- The legacy pending-answer classification incorrectly absorbs unrelated user messages when a pending question exists.
- The insurance-specific `user_need` reformulation amplifies the error but is not the root cause.

## Current architectural conclusion (ACA-304, RESOLVED by ACA-305A-D)

The immediate problem is not simply “topic shift detection.”

> ACA lacks an explicit, governed Mission Lifecycle Authority capable of reevaluating, suspending, replacing, completing or abandoning a mission from conversational evidence.

This is primarily an architecture-and-authority gap, with contributing semantic classification problems.

**Resolved.** `MissionManager` now holds exactly this authority via the `MissionTransitionProposal`/`MissionTransitionDecision` mechanism (ACA-305A-D). The exact conversation reproduced above no longer repeats a blind, unadapted question turn after turn: "¿Cómo estás?"/"Mis vacaciones" no longer get absorbed as answers to `user_need` (ACA-305D-RC2), the reformulated follow-up no longer leaks Galicia-insurance vocabulary into a `general_orientation` conversation (ACA-305D closing), and "¿Dios existe?" against an active insurance claim correctly engages that mission's own pre-existing recovery authority rather than looping (ACA-305D closing, `conversation_fulfillment.v1`). All six permanent fixtures reproducing this class of conversation pass (`tests/test_aca_305_mission_lifecycle_fixtures.py`), and the full suite is green. See `docs/architecture/ACA-305D_Mission_Lifecycle_Minimal_Controlled_Implementation.md` §10 for the closing evidence.

## Open roadmap items

### Required before controlled real-world testing

1. Establish a reproducible Git baseline for the current working tree. The working tree currently carries substantial uncommitted changes in an unrelated subsystem (LLM Verbalization / Conversational-First output layer — `step_handlers.py`, `conversation_objective.py`, `llm_verbalization.py`, `runtime.py` component-registry additions, plus several untracked Semantic Authority/Firewall files and docs) that were inspected during ACA-305A only far enough to confirm they have no mission-authority surface. They still need their own baseline/commit decision.
2. Formalize the freeze list: components and architectural areas that must not be modified during real-world testing without a new ADR.
3. Add the reproduced topic-shift conversation to the permanent conversational benchmark corpus as a regression fixture. **Still open** — the six ACA-305C fixtures exist and pass as executable tests (`tests/test_aca_305_mission_lifecycle_fixtures.py`), but were never additionally folded into the `benchmarks/conversations/` corpus as a standalone benchmark artifact. Low priority now that the underlying behavior is fixed and permanently regression-tested.
4. ~~Decide the authority model for mission lifecycle changes before implementing a fix.~~ **Closed by ACA-305A.** See `docs/architecture/ACA-305_Mission_Lifecycle_Authority_ADR.md`.
5. ~~Design the mission transition proposal/decision contract.~~ **Closed by ACA-305B.** See `docs/architecture/ACA-305B_Mission_Lifecycle_Contracts_and_Invariants.md`.
6. ~~Resolve mission/topic_stack integration (replace/abandon/suspend/resume vs. active/suspended topics and previous-topic navigation).~~ **Closed by ACA-305C.** See `docs/architecture/ACA-305C_Mission_Lifecycle_Benchmark_and_Integration_Closure.md`.
7. ~~Implement mission lifecycle authority; get all six ACA-305C fixtures and the full suite green.~~ **Closed by ACA-305D** (via RC1/RC2/RC3 audits + closing implementation). See `docs/architecture/ACA-305D_Mission_Lifecycle_Minimal_Controlled_Implementation.md` §10.

## Next recommended step

**ACA-305 (A-D, RC1-RC3) is complete.** The working tree is uncommitted and
ready for review; committing/pushing was explicitly not done this session,
per instruction, and remains a decision for the user. Two small, explicitly
deferred items remain, neither blocking, neither part of ACA-305's closing
conditions:

1. Topic id disambiguation (`mission:{type}` collision, ACA-305C §6) —
   still unreachable/unimplemented, since no proposal emitter requests
   `complete`/`abandon` for a mission-backed topic yet. Implement before any
   future sprint wires one.
2. Roadmap item 3 above (fold the six fixtures into the `benchmarks/
   conversations/` corpus as a standalone artifact, not just executable
   tests) — cosmetic/organizational, not a correctness gap.

With ACA-305 closed, the next body of work is whatever the user directs —
possibly resuming the roadmap item 1 baseline/commit decision for the
uncommitted LLM Verbalization / Conversational-First subsystem noted above,
which ACA-305 touched only far enough to confirm it has no mission-authority
surface.

Detection-quality improvement in the broader ACA-100 sense (lexical
whitelist expansion, semantic relevance classification) remains explicitly
out of scope for anything in the ACA-305 series and was not touched.

## Known constraints / do not reopen casually

- Do not add another independent Planner. ACA-305A confirmed `MissionManager` remains the sole writer of `active_mission`; do not reopen this without new evidence.
- Do not restructure `ConversationState` as part of the mission-lifecycle fix. ACA-305C's two required corrections (`_mission_impact_for`'s set membership, topic-id disambiguation) are narrowly-scoped fixes to already-existing, already-unconsumed logic — not a structural change — and should not be used as a wedge to widen scope further.
- Do not treat `active_mission` and `topic_stack` as needing a merged or shared writer. ACA-305C confirmed ownership stays split (`MissionManager` / `ConversationState`); only a synchronization contract was added between them.
- Do not broadly promote Semantic Authority based only on the official benchmark; adversarial performance remains materially weaker.
- Do not widen the `semantic_authority_pilot.py` promotion gate (`LOW_RISK_SEMANTIC_ACTS = {"greeting"}`) as a side effect of mission lifecycle work — ACA-305A found no evidence this is required; a mission-transition gate can consume Legacy-produced acts directly.
- Do not promote Candidate Work / Operational Governance / Operational Audit Ledger from Shadow without their own evidence and authority decision.
- Do not treat LLM verbalization as cognitive authority.
- Do not mix provisional and authoritative writes of the same artifact.
- Do not route new "unmatched pending slot" evidence through `auto_claim_guidance` — that mission type owns its own, separate, pre-existing recovery authority (`conversation_fulfillment.v1`, reask-via-reformulation), which a mission-lifecycle `suspend` proposal would contradict (ACA-305D closing §10.5's regression finding). The scoping guard (`_MISSION_TYPES_WITH_OWN_RECOVERY_AUTHORITY`) exists specifically to prevent this; do not remove it without re-verifying `test_conversation_fulfillment.py`.
- Do not write mission-transition-proposal rejection/unmatched evidence into `derived_state["slot_resolution"]` — that key's mere presence is read elsewhere (`_conversation_failed_steps`) as "a real resolution happened this turn." Use `derived_state["slot_resolution_evidence"]` for anything that isn't an actual accepted resolution.

## Important documents

Read these before changing direction:

1. `CURRENT_STATE.md`
2. `HANDOFF.md`
3. `docs/architecture/ACA-200_Core_Readiness_Audit.md`
4. `docs/architecture/ACA-300_Conversational_First_Architecture.md`
5. `docs/architecture/ACA-301_Operational_Work_Model_Second_Reassessment.md`
6. `docs/architecture/ACA-302_Real_World_Testing_Roadmap.md`
7. `docs/architecture/ACA-303_Observability_Completeness.md`
8. `docs/architecture/ACA-304_Cognitive_Audit_Mission_Persistence.md`
9. `docs/architecture/ACA-305_Mission_Lifecycle_Authority_ADR.md`
10. `docs/architecture/ACA-305B_Mission_Lifecycle_Contracts_and_Invariants.md`
11. `docs/architecture/ACA-305C_Mission_Lifecycle_Benchmark_and_Integration_Closure.md`
12. `docs/architecture/ACA-305D_Mission_Lifecycle_Minimal_Controlled_Implementation.md` — **partial/not closed**, read its §8 before resuming this track
13. `docs/architecture/ACA-305D-RC1_Pending_Slot_Resolution_Boundary_Audit.md` — root-causes fixtures 1-3 (and separately, fixture 4); read its §10 before authorizing any fix to `resolve_pending_slot_answers`
14. `docs/architecture/ACA-305D-RC3_Reformulation_Mechanism_Audit.md` — root-causes why fixtures 1/3's response text stayed red after RC2; read its §6 before authorizing the two-edit minimal fix
15. ACA-019 / ACA-024 for prior authority and forensic findings

## Update rule

This file must be updated at the end of every meaningful sprint or architecture investigation.

A sprint is not considered closed until this file reflects:

- what changed;
- what evidence supports it;
- what decisions were made;
- what remains open;
- the next recommended step.

If this document conflicts with code or tests, code and tests win and the discrepancy must be reported and corrected here.

