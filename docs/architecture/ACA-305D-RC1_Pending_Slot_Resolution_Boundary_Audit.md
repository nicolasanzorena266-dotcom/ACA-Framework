# ACA-305D-RC1 - Pending Slot Resolution Boundary Audit

Status: Investigation only. No code, test, or contract was modified. ACA-305D
remains IN PROGRESS, not closed, not reverted. This document does not
implement a fix; it determines precisely why `resolve_pending_slot_answers`
absorbs low-specificity or unrelated messages before mission-reevaluation
evidence can ever reach `MissionManager`, and what closing that gap would
require.

Every claim below was re-verified against the working tree on this date, in
continuation of the same uncommitted ACA-305D changes (`git status` shows no
drift beyond what ACA-305D already landed).

## 0. The Question

> ¿Por qué `resolve_pending_slot_answers` absorbe mensajes de baja
> especificidad o no relacionados antes de que la evidencia pueda llegar al
> mecanismo de reevaluación de misión?

## 1. Real Execution Flow

Traced through `ConversationManager.begin_turn` (`aca_os/conversation_manager.py:127-249`)
in exact call order, with the file:line of each step:

| Order | Step | Location | What it decides |
| --- | --- | --- | --- |
| 1 | `SemanticAuthority.interpret` + `SemanticProjector.project` | `conversation_manager.py:~150-190` | Computes a shadow semantic representation/projection (act, goal, entities) -- always computed, not yet authoritative for most acts. |
| 2 | `select_conversational_act_authority` (SA-3 gate) | `conversation_manager.py:~190` (`semantic_authority_pilot.py:25-90`) | Chooses Legacy or Semantic as the authoritative act for this turn. Promotes Semantic only for `greeting`-type acts (`LOW_RISK_SEMANTIC_ACTS = {"greeting"}`, `semantic_authority_pilot.py:17`) -- everything else, including every act relevant to this audit, rolls back to Legacy. |
| 3 | `recognize_conversational_act` (Legacy) | `conversation_state.py:3958-3987`, feeding `_conversation_act_candidates` (`conversation_state.py:3990-...`) and `_select_conversational_act` (`conversation_state.py:4230-4251`) | **Sets `conversation_state.last_conversational_act` for this turn.** This is the single most consequential step for this audit -- see section 3. |
| 4 | `resolve_pending_slot_answers` | `conversation_state.py:941-1016`, called at `conversation_manager.py:203` | **The function under audit.** Runs immediately after act recognition, before anything else. |
| 5 | `assimilate_user_facts` | `conversation_state.py:4829-...`, called at `conversation_manager.py:205` | `_advance_mission`'s fact/slot-driven mission advancement (ACA-305D's migrated proposal emitter). |
| 6 | `update_topic_stack` | `conversation_state.py:3330-3476`, called at `conversation_manager.py:206` | Topic navigation; also where ACA-305D's `_topic_shift_mission_proposal` (`conversation_state.py:3478-3530`) emits `suspend`/`resume` mission proposals. |
| 7 | `project_conversational_goal` / `apply_conversational_goal` | `conversation_manager.py:217-239` | Computes `mission_impact` (`may_change_mission_state`, `preserve_active_mission`) and `abandonment_criteria` -- the signals ACA-305C/305D wired `MissionManager` to eventually consume. |
| 8 | `to_cognitive_state` | `conversation_manager.py:246` | Projects `ConversationState` (already carrying whatever step 4 decided) into `CognitiveState`. |
| 9 | `MissionManager.before_kernel` | `runtime.py:588-592`, `mission_manager.py:71-104` | Evaluates `mission_transition_proposals` collected in `conversation_state.derived_state` and applies at most one transition. |

**The decisive structural fact**: `resolve_pending_slot_answers` (step 4) runs
*before* topic-shift detection (step 6), *before* `mission_impact`/
`abandonment_criteria` are computed (step 7), and *long before*
`MissionManager` ever runs (step 9). None of ACA-305D's new proposal
machinery exists yet, in this turn, at the point `resolve_pending_slot_
answers` makes its decision. By the time any mission-transition-evidence
code runs, if step 4 has already absorbed the message, that absorption is
already baked into `ConversationState.slots`/`active_mission`/`confirmed_
facts` and cannot be un-done downstream. **This is a sufficient, structural
explanation for why ACA-305D's implementation -- however correctly built --
could never have fixed fixtures 1-3 without also touching this boundary.**

Step 3 (act recognition) happens *before* step 4, and step 4 reads its
result (`conversation_state.last_conversational_act`) as a gate (section 3).
So the true causal order relevant to this audit is: **act recognition
decides first; slot resolution either defers to that decision or, per
section 3's finding, is driven by the exact same matching logic that
decided it.**

## 2. Current Ownership

Unchanged from before this audit, and confirmed still accurate:
`ConversationState` owns `slots`, `pending_questions`, `confirmed_facts`
(`conversation_state.py:682-731`'s field-ownership table). `resolve_
pending_slot_answers` is a `ConversationState` method
(`conversation_state.py:577-578`), consistent with that ownership. This
audit does not find an ownership violation in the ACA-305A/B sense
(no second writer of `CognitiveState.active_mission` is created here --
`resolve_pending_slot_answers` only ever calls `replace(conversation_state,
...)`, never `CognitiveState.evolve(...)`).

What this audit finds is different in kind from the ACA-305A/B/C findings:
not a *second authority over the same field*, but **a single authority
(`ConversationState`) making a binding, unreviewable decision with no
rejection path**, several steps upstream of where any review could occur.

## 3. De Facto Authority: Classification or Decision?

**`resolve_pending_slot_answers` takes a de facto conversational decision,
not merely a classification.** Evidence:

- It writes `slots[slot_name]` (line 977), `confirmed_facts[slot_name]`
  when closed (line 979), removes the question from `pending_questions`
  when closed (lines 980-984), and rewrites `active_mission` via `_mission_
  with_slots` (line 994) -- all unconditionally, the moment a match is
  found. There is no subsequent step, in this turn or any later one, that
  reviews or can veto this write. Compare to `_advance_mission` before
  ACA-305D (ACA-305A section 1.3-1.4): that was already flagged as a de
  facto authority problem, and even *it* did not close `pending_questions`
  or write `confirmed_facts` directly -- `resolve_pending_slot_answers` is
  structurally *more* authoritative, not less, and was not part of ACA-305A/
  B/C's audited surface.
- The existing architecture graph already classifies it this way:
  `authority_dependency_graph.py:288` declares
  `_TransitionSpec("resolve_pending_slot_answers", "user_text", "slot_state",
  "conversation_state", "conversation_manager", "legacy_interpretation",
  "legacy_primary", "persistent_state_update")` -- `"legacy_primary"` is the
  same authority-mode label given to direct, unconditional, un-gated writes
  elsewhere in that graph (e.g. `recognize_conversational_act` itself,
  `update_topic_stack`), as opposed to `"atomic_conditional"`/`"semantic_
  conditional"` labels used for gated selections like `select_conversational_
  act_authority`. This was already correctly labeled in ACA-033's own
  tooling; no prior sprint drilled into what that label concealed.

## 4. Exact Call Order Relative to the Six Named Mechanisms

Directly answering the sprint's question 3:

| Mechanism | Relative order | Evidence |
| --- | --- | --- |
| Topic shift detection | **After** slot resolution | `update_topic_stack` at `conversation_manager.py:206`, `resolve_pending_slot_answers` at line 203. |
| Mission reevaluation (`MissionManager`) | **Long after** slot resolution -- outside `begin_turn` entirely | `MissionManager.before_kernel` at `runtime.py:588`, called after `ConversationManager.begin_turn` returns. |
| `ConversationState` | Slot resolution is itself a `ConversationState` method; it is the second state-mutating step in `begin_turn` (after act recognition). | `conversation_state.py:577-578`, `941-1016`. |
| `SemanticAuthority` | **Before** slot resolution, but its output is discarded for this case | Steps 1-2 in section 1's table; SA-3 promotes only `greeting`, so the act slot resolution reads (step 3) is always Legacy's for the messages this audit concerns. |
| `MissionManager` | Same as "mission reevaluation" above. | -- |
| Pending questions | Read and mutated *by* slot resolution itself (`conversation_state.pending_questions`, lines 952, 980-984). | -- |
| Slot fulfillment | *Is* slot resolution's own output; there is no separate "slot fulfillment" step downstream that could re-check it. | -- |

## 5. What Messages Does It Consider Valid Answers?

`resolve_pending_slot_answers` (line 958-963) tries, in order:

1. `_explicit_slot_matches` (`conversation_state.py:6193-6199`): for every
   pending slot, an explicit match via `_match_slot_answer`
   (`6218-6229`), which dispatches to a slot-specific matcher.
2. If no explicit match and pending slots exist, `_contextual_slot_match`
   (`6202-6216`): tries **only the single highest-priority pending slot**
   (`primary_slot = pending_slots[0]`, line 6209) with `contextual=True`.

Slot-specific matchers (`_match_slot_answer`, line 6218-6229):

- `injuries` -> `_match_injuries` (`6232-6280`): explicit positive/negative
  term lists (`"no hubo lesionados"`, `"heridos"`, etc.) plus an
  uncertainty branch. **Returns `None` -- a real rejection -- when nothing
  matches.**
- `user_role` -> `_match_user_role` (`6283-6348`): explicit
  insured/third-party term lists, plus a narrow contextual-affirmation
  branch gated on the pending question's own prompt text containing
  `"asegurado"`. **Also returns `None` when nothing matches.**
- **Every other slot name** (today, only `user_need`) ->
  `_match_generic_slot` (`6351-6362`):

  ```python
  def _match_generic_slot(slot_name, normalized, *, contextual):
      if not contextual or _is_uncertain(normalized) or len(normalized) < 2:
          return None
      return _slot_match(
          slot=slot_name, value=normalized, confidence=0.5,
          status=SlotStatus.PARTIALLY_FILLED, evidence=normalized,
          reason="generic_contextual_slot_answer", close=False,
      )
  ```

  **This is the entire relevance check: not empty, not in an 8-phrase
  "uncertain" whitelist (`_is_uncertain`, `6489-6504`: `"no se"`, `"no
  estoy seguro/a"`, `"creo que no/si"`, `"tal vez"`, `"quizas"`), and at
  least 2 characters long.** There is no positive-relevance requirement of
  any kind.

## 6. Specificity / Confidence Criteria Actually Used

- `_match_injuries`/`_match_user_role`: confidence is a small, hand-tuned
  set of constants (0.86-0.92) tied to which explicit term matched, plus
  0.45 for the uncertainty branch, plus 0.74 for the narrow contextual-yes
  branch. These are **relevance-gated by construction** -- confidence is
  only ever assigned after a real lexical match; there is no path to a
  confidence value without one.
- `_match_generic_slot`: a single hardcoded confidence, **0.5**, assigned
  regardless of what the 2+ characters actually say. This is the *lowest*
  confidence value computed anywhere in this matching layer -- and it is
  the value assigned specifically to the cases with the *least* relevance
  evidence behind them.
- **Critically: this confidence value is never read by anything.**
  `resolve_pending_slot_answers`'s loop (`conversation_state.py:965-984`)
  applies every match in `explicit_matches` unconditionally; there is no
  `if match["confidence"] >= threshold` anywhere in this function or its
  callers. The field exists (it flows into the slot's own `confidence`
  attribute, and into `_slot_transition`'s trace, `6415-6428`), but nothing
  in the accept/reject path ever consults it. This is the same category of
  gap ACA-305B/`semantic_authority_pilot.py` exists specifically to close
  for conversational acts and mission transitions (`SEMANTIC_ACT_MIN_
  CONFIDENCE`, `MINIMUM_CONFIDENCE` per transition type) -- it was simply
  never extended to this layer.

## 7. Why Each of the Four Messages Is Absorbed (or, for One, Isn't)

This audit found **fixture 4 has a materially different root cause than
fixtures 1-3.** Verified by tracing each message through section 5's logic:

| Message | Pending slot | Matcher | Result | Why |
| --- | --- | --- | --- | --- |
| `"¿Cómo estás?"` | `user_need` (`general_orientation`) | `_match_generic_slot` | **Absorbed**, `PARTIALLY_FILLED`, confidence 0.5, value = the raw message | Not empty, not in the 8-phrase uncertainty list, length >= 2. No relevance check exists to fail. |
| `"Mis vacaciones"` | `user_need` | `_match_generic_slot` | **Absorbed**, same shape | Same reason. |
| `"Ninguno"` | `user_need` | `_match_generic_slot` | **Absorbed**, same shape | `"ninguno"` is not in `_is_uncertain`'s whitelist (which has `"no se"`, `"tal vez"`, etc. but not `"ninguno"`) and is not in `_is_negation`'s whitelist either (`{"no", "nop", "para nada", "negativo"}`, `conversation_state.py:6045-6052` -- confirmed unchanged from ACA-304's finding). It falls through both narrow checks into the generic catch-all. |
| `"¿Dios existe?"` | `injuries` (`auto_claim_guidance`, higher priority than `user_role`) | `_match_injuries` | **Not absorbed** -- returns `None` | `_match_injuries` has no generic fallback; "dios existe" matches neither the negative nor positive term lists, and `_contextual_slot_match` only ever tries the single highest-priority pending slot (line 6209), so `user_role` is never even attempted. |

For `"¿Dios existe?"`, `resolve_pending_slot_answers` correctly does
nothing (`resolutions` stays empty, function returns `conversation_state,
[]` unchanged at line 991-992). **Fixture 4's failure is not an absorption
problem at all.** It is the absence of any consumer for a *rejected* match:
when `_contextual_slot_match` returns `None`, that non-match carries no
signal anywhere -- it is not recorded, not classified as `unrelated`, and
never becomes evidence for anything. The turn falls through to `intent=
fallback` (the zero-cost `IntentMatcher` finds no rule) and `_advance_
mission` simply recomputes the same `waiting_user` state from unchanged
facts. This distinction matters directly for section 12/13's recommended
fix shape: fixtures 1-3 need a **rejection path with a confidence floor**;
fixture 4 needs a **positive record of "nothing matched"** to exist at all,
so something downstream can treat that absence as its own kind of evidence.

## 8. A Single Shared Root Cause, Not Two Independent Ones

This is the most important structural finding of this audit. `_looks_like_
pending_answer` (`conversation_state.py:6014-6025`), the function that
decides whether a `PENDING_ANSWER` conversational-act *candidate* even
exists (used inside `_conversation_act_candidates`, `conversation_state.py:
4026`), is:

```python
def _looks_like_pending_answer(normalized, pending_slots, pending_questions):
    if not pending_slots:
        return False
    explicit = _explicit_slot_matches(normalized, pending_slots)
    if explicit:
        return True
    contextual = _contextual_slot_match(normalized, pending_slots, pending_questions)
    return contextual is not None
```

**This calls the exact same `_explicit_slot_matches`/`_contextual_slot_
match` functions `resolve_pending_slot_answers` later calls to perform the
actual absorption.** They are not two independently-behaving mechanisms
that happen to agree; they are the same matching logic invoked twice --
once (earlier, at act-recognition time, section 1 step 3) to decide whether
a `PENDING_ANSWER` act candidate exists at all, and once (section 1 step 4)
to perform the write. A fix to `_match_generic_slot`'s permissiveness
therefore automatically and correctly propagates to both call sites,
because there is only one implementation to fix.

This also explains why `_act_suppresses_slot_resolution`
(`conversation_state.py:4263-4273`, which already lists `TOPIC_SHIFT` among
the acts that suppress slot resolution entirely) never engages for these
four messages: `TOPIC_SHIFT`'s own candidate generation
(`_mentions_topic_shift`, a separate lexical whitelist, `conversation_state.
py:4071` calling into the function ACA-304 already found too narrow) never
fires for any of "¿Cómo estás?" / "Mis vacaciones" / "Ninguno" / "¿Dios
existe?" -- so there is no competing `TOPIC_SHIFT` candidate for the
selection step to weigh against `PENDING_ANSWER`. **The suppression
mechanism is sound and already correctly wired; it simply never gets a
chance to fire, because nothing else recognizes these messages as anything
more specific.**

One further, precise sub-finding: act selection
(`_select_conversational_act`, `conversation_state.py:4230-4251`) sorts
candidates by `(confidence, priority)` -- **confidence first, priority only
as a tiebreaker** (line 4248: `key=lambda item: (float(item.get(
"confidence") or 0.0), priority.get(...))`). This means the commonly-cited
"`PENDING_ANSWER` priority 95 beats `TOPIC_SHIFT` priority 86" framing
(ACA-304, restated in earlier sprints) is not, in fact, how selection
works when both candidates exist with different confidences -- priority
only matters on an exact confidence tie. For these four messages the point
is moot (no `TOPIC_SHIFT` candidate exists to compete), but it is a
correction worth recording precisely: **the real defect is not priority
ordering; it is candidate generation** (`_looks_like_pending_answer`
returning `True` on evidence that should not qualify) **combined with a
confidence value that is computed but never gated.**

Also notable, and worth naming even though it does not change this
sprint's fixtures: `PENDING_ANSWER`'s act-level confidence (0.82 for a
contextual match, `conversation_state.py:4033`) is a hardcoded constant
**independent of** the underlying slot match's own confidence (0.5, from
`_match_generic_slot`). A generic, no-relevance-check catch-all match is
reported to the act-selection layer as a fairly confident interpretation
(0.82) even though the evidence behind it is, by the matcher's own
scoring, the least confident category the system computes (0.5). This
inconsistency is not the direct cause of any of the four fixtures (again,
because no competing candidate exists to be out-scored), but it would
matter the moment a competing low-confidence `TOPIC_SHIFT`/`unrelated`
candidate did exist, and is worth fixing alongside any threshold work.

## 9. Classification Matrix -- Where the Error Actually Lives

Directly answering the sprint's question 7 (matching / precedencia /
ausencia de rechazo / confianza / fallback / ownership / combinación):

| Candidate cause | Applies? | Evidence |
| --- | --- | --- |
| **Matching** (over-permissive positive match) | **Yes -- primary, for fixtures 1-3.** | `_match_generic_slot` has no relevance check at all (section 5, 7). |
| **Precedencia** (priority table ordering) | **No**, for these four messages specifically; the mechanism exists but is never exercised, since no competing candidate is ever generated (section 8). Real in principle, not causal here. | `_select_conversational_act` sorts confidence-first (section 8). |
| **Ausencia de rechazo** (no path to a "not an answer" outcome) | **Yes -- primary, for fixture 4; contributing for 1-3.** | Section 7: a `None` from `_contextual_slot_match` produces no record, no evidence, nothing (fixture 4). For fixtures 1-3, even though a "rejection" *could* happen (the generic matcher could decline), no floor exists that would ever cause it to. |
| **Confianza** (confidence miscalibration/non-use) | **Yes -- contributing, for all four.** | Section 6: confidence is computed (0.5) but never gated; act-level confidence (0.82) does not derive from the underlying match's own confidence (section 8). |
| **Fallback** (the generic catch-all's design) | **Yes -- primary, for fixtures 1-3.** | `_match_generic_slot` *is* a fallback mechanism, by name and by design; the fallback itself is where the missing floor lives (section 5). |
| **Ownership** | **No.** | Section 2: no second writer of any authoritative field was found; this is a single-authority, no-review problem, not a duplicate-authority problem. |
| **Combinación** | **Best answer overall.** Matching + fallback design + absent confidence gate + absent rejection state, acting together, at a point structurally upstream of every mission-reevaluation mechanism this series of sprints has built. Precedence and ownership are not causal here. | Sections 5-8. |

## 10. Scope Decision: ACA-305D, a Separate Sprint, or an ACA-305C Amendment?

This audit does not decide this unilaterally -- it presents the evidence
needed to decide it, per the sprint's own instruction not to implement.

**Arguments that a minimal fix is in-scope for ACA-305D:**

- The fix this audit's evidence points toward (section 12-13) is a
  **confidence-threshold gate**, not a semantic relevance classifier. It
  reuses a pattern already proven twice in this codebase this series
  (`semantic_authority_pilot.py`'s `SEMANTIC_ACT_MIN_CONFIDENCE`/
  `SEMANTIC_GOAL_MIN_CONFIDENCE`; ACA-305D's own `MINIMUM_CONFIDENCE` per
  transition type in `mission_manager.py`). It does not require improving
  *what* `_mentions_topic_shift`/`_match_generic_slot` recognize -- only
  gating *whether a low-confidence recognition is accepted* -- which is
  squarely mission/evidence-authority work, the category ACA-305A/B/C/D
  all treat as in-scope, not the "cognitive"/detection-quality dimension
  ACA-304 explicitly separated out.
- `resolve_pending_slot_answers` was not *excluded* from ACA-305D by name
  in any prior document -- it was simply not yet audited. Its omission was
  a gap in coverage, not a deliberate scope boundary the way ACA-304
  Option 2 (lexical whitelist improvement) or SA-3 gate widening were
  explicitly named and excluded in ACA-305A section 11 / ACA-305B section
  20 / ACA-305C section 13.

**Arguments that it requires an explicit amendment:**

- `resolve_pending_slot_answers` and `_looks_like_pending_answer` were
  genuinely never named, audited, or scoped in ACA-305A, ACA-305B, or
  ACA-305C. Touching them was not something any prior document authorized,
  even implicitly -- ACA-305D's own closure document (section 4) named
  `resolve_pending_slot_answers` only as the *cause*, not as pre-approved
  surface to modify.
- The fix, even framed as "just a threshold," still changes user-visible
  behavior for real conversations today accepted by `_match_generic_slot`
  (section 11 discusses exactly what could change). That is a larger
  behavioral surface than any single change ACA-305D has made so far, and
  deserves the same explicit sign-off ACA-305D's own closure document
  asked for rather than assuming.

**This audit's position**: the minimal fix in section 13 is small,
reversible, and consistent with already-approved patterns -- but because it
touches a component no prior sprint in this series named as in-scope, and
because the sprint that requested this audit explicitly said "no
implementes todavía," this should be treated as **a scope decision for the
user to make explicitly** (a short amendment to ACA-305D's mandate, not a
new architecture document) rather than something this audit or a
follow-up implementation assumes permission for.

## 11. Regression Risks of Tightening This Matching

- `_match_generic_slot` is, today, the **only** matcher for any slot other
  than `injuries`/`user_role` -- currently that means only `user_need`
  (`general_orientation`'s single slot). Tightening it changes behavior
  for every `general_orientation` conversation, not a narrow subset.
- Legitimate but terse, real answers to `user_need` (e.g. a two-or-three
  word real need like `"un choque"` or `"una consulta"`) currently pass
  through the *same* no-floor path as `"Mis vacaciones"`/`"¿Cómo estás?"`.
  A confidence floor that is too strict risks rejecting genuinely relevant
  short answers, not just irrelevant ones -- there is no existing signal
  in `_match_generic_slot` that distinguishes "terse but relevant" from
  "terse and irrelevant"; both currently score the same flat 0.5.
- `_is_uncertain`'s 8-phrase whitelist (section 5) is itself narrow and
  was not exercised or re-validated by this audit; changes near it could
  have their own edge effects independent of any confidence-threshold
  work.
- `injuries`/`user_role` are unaffected by any change scoped to `_match_
  generic_slot` specifically -- they have their own dedicated matchers
  with explicit term lists and already-real rejection (`None`) paths
  (section 5). `test_slot_lifecycle.py::test_contextual_yes_resolves_
  user_role_after_pending_question` (verified read during this audit)
  exercises `_match_user_role`'s contextual-yes branch, not `_match_
  generic_slot`, and would not be affected by a generic-slot-scoped fix.
- Any future mission type that adds a new slot name (anything besides
  `injuries`/`user_role`) automatically inherits whatever `_match_generic_
  slot` becomes -- both today's permissiveness and any future floor. A fix
  here is not `general_orientation`-specific; it is the default behavior
  for all not-yet-specialized slots.

## 12. Benchmarks/Tests Depending on Minimal Valid Answers

Searched (`tests/`, by name and by content) for direct references to
`resolve_pending_slot_answers`, `_contextual_slot_match`, `_match_generic_
slot`, `"Ninguno"`, and minimal-answer scenarios:

- **No test references these internal functions by name.** All coverage of
  this behavior is indirect, through full multi-turn Runtime conversations.
- **`test_slot_lifecycle.py::test_contextual_yes_resolves_user_role_after_
  pending_question`** is the one existing test directly exercising
  contextual minimal-answer resolution (`"Si"` after a pending `user_role`
  question). It goes through `_match_user_role`'s dedicated contextual-yes
  branch (section 5), not `_match_generic_slot` -- **unaffected** by a
  generic-slot-scoped confidence floor.
- **No test found** that requires an unrelated or low-specificity message
  to be accepted as a `user_need`/generic-slot answer. This audit found no
  existing test that a `_match_generic_slot` confidence floor would
  definitively break -- but this was verified by search, not by running
  the suite (out of scope for an audit that must not implement or execute
  changes); an actual implementation attempt must still run the full suite
  to confirm, per ACA-305D's own established discipline.
- Numbers, dates, and other elliptical-answer categories the sprint brief
  asks about: **no dedicated matcher or test exists for these today at
  all** -- `_match_injuries`/`_match_user_role` are lexical-term-list
  matchers with no date/number parsing, and `_match_generic_slot` would
  currently accept a bare number or date as a generic `user_need` answer
  exactly as permissively as it accepts any other 2+ character string.
  There is no existing, working number/date-answer behavior this audit
  can confirm would be preserved or broken -- it appears not to exist as a
  distinct capability today, only as an unremarked instance of the same
  generic permissiveness.

## 13. Minimal Change That Would Let Unrelated Evidence Reach `MissionManager`

Presented as the shape of a fix, not an implementation (no code was
written):

1. **Add a confidence floor to `_match_generic_slot`'s consumption**, not
   necessarily to the matcher itself -- e.g., `resolve_pending_slot_
   answers` (or a thin wrapper around `_explicit_slot_matches`/`_
   contextual_slot_match`) treats a match whose `confidence` is below a
   threshold (the matcher's own current output, 0.5, is already the
   natural candidate for "below the bar") as **not an accepted answer**.
   Since `_match_generic_slot`'s only output value is exactly 0.5 today,
   this could be as small as: contextual generic matches no longer close
   or partially-fill the slot by default; they become a distinct outcome
   (section 14) instead.
2. **That distinct outcome becomes a new evidence source** for the
   `mission_transition_proposals` mechanism ACA-305D already built
   (`conversation_state.py:derived_state["mission_transition_proposals"]`,
   consumed by `evaluate_mission_transition_proposals` in `mission_
   manager.py`) -- mirroring exactly how ACA-305D's `_topic_shift_mission_
   proposal` (`conversation_state.py:3478-3530`) already turns a topic-
   stack event into inert evidence for `MissionManager` to evaluate, never
   a direct write. A rejected/low-confidence slot match would emit a
   `maintain` (at minimum, to avoid silently repeating the exact same
   question) or, when corroborated by other signals ACA-305B/C already
   named (`abandonment_criteria`, `TOPIC_SHIFT`), a `replace`/`abandon`
   proposal -- with `MissionManager` remaining the sole acceptor, per
   section 10's "no parallel authority" requirement.
3. **Symmetrically, fixture 4's gap (section 7) needs the "no match found
   at all" case to also produce a record**, not silently return early
   (`conversation_state.py:991-992`) -- at minimum a trace entry, so a
   downstream evidence source has something to read even when nothing
   matched.

This shape requires **no change to `_mentions_topic_shift`, `SemanticAuthority`,
or any lexical whitelist** -- it does not improve detection of what a
message *is*; it only stops treating a low-confidence, no-relevance-check
match as equivalent to a real answer, using a confidence value the system
already computes today and simply never consults.

## 14. Does Slot-Match Outcome Need a Richer Taxonomy?

**Yes.** Today there are exactly two outcomes: silently matched (absorbed,
regardless of confidence) or silently absent (no record at all). Section
7's finding that fixtures 1-3 and fixture 4 have different root causes maps
directly onto the sprint's proposed taxonomy:

- `answered`: an explicit, term-list-backed match (`_match_injuries`/
  `_match_user_role`'s positive paths) -- unaffected by this audit's
  findings, already correctly gated by real relevance evidence.
- `rejected_as_answer`: a generic/contextual match was attempted and found
  below the confidence floor (section 13, point 1) -- this is the new
  state fixtures 1-3 need to exist.
- `ambiguous`: reserved for a case not evidenced by this audit (e.g.
  `_resolve_topic_reference`'s existing `ambiguity` output,
  `conversation_state.py:3377-3379`, is a working precedent for this
  category elsewhere in the codebase) -- not required to fix the four
  fixtures, but a natural taxonomy neighbor.
- `unrelated`: the case fixture 4 needs (section 7, section 13 point 3) --
  no slot pattern matched at all, and that absence itself becomes a
  positive record rather than silence.
- `topic_shift_candidate`: not evidenced as separately needed by this
  audit -- `TOPIC_SHIFT` already has its own, independent detection path
  (`_mentions_topic_shift`) and its own act-candidate machinery; slot
  resolution does not need to duplicate that classification, only to stop
  competing with it via `_looks_like_pending_answer`'s permissiveness
  (section 8).

Minimum required for the four fixtures: distinguishing `answered` from
`rejected_as_answer` (fixtures 1-3) and from `unrelated`/no-record-at-all
(fixture 4). `ambiguous`/`topic_shift_candidate` are not evidenced as
required by this specific audit, though they may be natural to add for
symmetry with `ambiguity` handling already present in the topic layer.

## 15. Observability Gaps

- `resolve_pending_slot_answers`'s trace (`derived_state["slot_
  resolution"]`, `conversation_state.py:995-1001`) **only exists when at
  least one resolution occurred** -- the early-return path
  (`conversation_state.py:991-992`, `if not resolutions: return
  conversation_state, []`) produces no trace at all. There is currently no
  way to reconstruct, from any trace, whether the system considered and
  rejected a message as a slot answer versus never attempted to match it
  in the first place. This is the same category of gap ACA-305B section
  11 already closed for mission decisions (rejections are recorded, not
  silent) -- it has not yet been extended to this layer.
- The act-recognition trace (`derived_state["conversation_act"]`,
  `conversation_state.py:3965-3975`) *does* record every candidate
  considered, including confidence (this already exists and is good
  precedent) -- but it does not record *why* `_looks_like_pending_answer`
  returned `True` (i.e., it does not surface which underlying slot match,
  with what confidence, drove the `PENDING_ANSWER` candidate's existence).
  Reconstructing section 8's finding required reading source code, not
  querying a trace.
- Neither trace today would let an auditor answer, from data alone,
  "was this message accepted as a `user_need` answer with high or low
  confidence" -- the `slots` field on the resulting mission/`ConversationState`
  does carry the assigned `confidence` (visible in this audit's earlier
  diagnostic dumps, e.g. `"confidence": 0.5`), but only for the accepted
  case; there is nothing for the rejected or absent cases (mirroring the
  same "confidence computed, not surfaced for decision-making" gap
  identified in section 6).

## Summary Table

| Sprint question | Answer |
| --- | --- |
| 1. Conceptual authority today | De facto binding decision authority, not mere classification -- unreviewable, unvetoable (section 3). |
| 2. Classifies or decides? | Decides (section 3). |
| 3. Exact order vs. the six mechanisms | Section 4 -- runs after act recognition, before topic shift/mission reevaluation/`MissionManager`. |
| 4. What counts as a valid answer | Section 5 -- explicit term-list matches for `injuries`/`user_role`; anything 2+ chars, not in an 8-phrase whitelist, for everything else. |
| 5. Specificity/confidence criteria | Section 6 -- computed (0.5 for generic) but never gated anywhere. |
| 6. Why the four messages are absorbed | Section 7 -- three by the generic-slot no-floor path; the fourth is not absorbed at all, and fails for the opposite reason (no rejection record). |
| 7. Matching / precedence / rejection / confidence / fallback / ownership / combination | Combination -- matching + fallback design + absent confidence gate + absent rejection state are primary; precedence and ownership are not causal here (section 9). |
| 8. Scope: ACA-305D / separate sprint / ACA-305C amendment | Left as an explicit decision for the user (section 10); this audit's position is a small amendment, not a unilateral in-scope call. |
| 9. Which component should decide "not an answer" | `ConversationState` (unchanged ownership) proposes; `MissionManager` remains sole decider, per the pattern ACA-305D already built (section 13). |
| 10. Avoiding a second parallel authority | Route the new "rejected"/"unrelated" signal through the existing `mission_transition_proposals` mechanism -- no new gate, no new authority (section 13). |
| 11. Regression risks | Section 11 -- scoped to `user_need`/future generic-slot types; `injuries`/`user_role` unaffected; terse-but-relevant answers are the main risk. |
| 12. Benchmarks depending on minimal answers | Section 12 -- one relevant test found, unaffected; no test found that a generic-slot floor would break; number/date handling does not exist today as a distinct, tested capability. |
| 13. Minimal fix shape | Section 13 -- confidence floor + route rejection into existing proposal mechanism; no detection-quality change required. |
| 14. Need for a richer taxonomy | Yes, at minimum `answered` / `rejected_as_answer` / `unrelated` (section 14). |
| 15. Missing observability | Section 15 -- no trace at all on the "nothing matched" path; no visibility into which match drove `PENDING_ANSWER` candidacy. |

## Recommendation

Do not implement yet, per this sprint's instruction. The evidence above
supports a small, reversible, pattern-consistent fix (section 13) that
would plausibly resolve fixtures 1-3 and enable fixture 4's resolution
once paired with the `abandonment_criteria`/`unrelated`-evidence work
ACA-305D's own closure document already flagged as needed. Because the
component this fix touches (`resolve_pending_slot_answers`/`_looks_like_
pending_answer`) was never previously named as in-scope by ACA-305A,
ACA-305B, or ACA-305C, this audit recommends the user explicitly decide
section 10's scope question -- via a short, explicit amendment to ACA-305D's
mandate -- before any implementation begins. `CURRENT_STATE.md` is updated
to record this audit's conclusion, since it is a code-backed finding, without
declaring ACA-305D closed or authorizing implementation.
