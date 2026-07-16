# ACA-305D-RC3 - Reformulation Mechanism Audit

Status: Investigation only. No code, test, or contract was modified.
ACA-305D remains IN PROGRESS. This document does not implement a fix.

Every claim below was re-verified against the working tree on this date, in
continuation of the same uncommitted ACA-305D/RC1/RC2 changes (`git status`
shows no drift beyond what those sprints already landed).

## 0. The Question

> ¿El mecanismo de reformulación de preguntas constituye un bug, una
> decisión histórica, o una autoridad conversacional incompleta?

**Answer, stated up front and evidenced below**: it is a **historical,
deliberate UX decision** ("don't repeat a question in the exact same words
twice") **that has become an incomplete conversational authority** once
measured against the evidence-and-authority discipline ACA-305A-D
established. It was reasonable in isolation when written; it predates, and
is structurally blind to, every mission-authority signal this series has
since built (`resolve_pending_slot_answers`'s outcome, `MissionTransitionDecision`,
explicit rejection evidence). It is not a "bug" in the sense of a coding
mistake — every function audited here does exactly what it was written to
do — but it is also not a complete mechanism relative to what ACA-305 now
requires of anything that decides what the user sees after a slot
answer is judged.

## 1. Exhaustive Callers and Flow

### 1.1 Call graph

```
plan_conversational_response(conversation_state, message)      [conversation_state.py:1495]
  -> _selected_required_information(...)                       [2334]
       -> _maybe_reformulate_required_question(...)            [2369]   <- the only caller of both audited functions
            -> _should_reformulate_selected_question(slot, ...) [2397]
            -> _reformulated_question_for_slot(slot, ...)       [2417]
  -> NarrativeResponseComposer reads required_information[0]["question"]
       (narrative_response_composer.py:244, 333)
```

**There is exactly one call site** for each audited function, both inside
`_maybe_reformulate_required_question` (lines 2381-2387). Nothing else in
`aca_os/` calls either function directly.

### 1.2 Exact turn-level ordering

`plan_conversational_response` runs from `runtime.py` **after**
`MissionManager.before_kernel` and after `operational_conversation_state`
has been reprojected from the mission-decided `CognitiveState`
(the FW-11 comment at `runtime.py:597-604`, re-confirmed unchanged this
session). So, contrary to what might be assumed, **this mechanism runs
late enough in the turn to see MissionManager's decision** — the ordering
is not the obstacle. What it actually consults, once it runs, is section 5.

### 1.3 What builds its inputs

- `conversation_plan` comes from `_conversation_plan_from_state`
  (`1730-1737`), which reads the SAME turn's freshly-computed
  `derived_state["conversation_plan"]` trace (populated moments earlier by
  `plan_conversation` in the same `runtime.py` sequence, line ~611-613).
- `conversation_plan["previous_plan"]["active_plan"]["current_step"]`
  is what `_should_reformulate_selected_question` actually reads
  (`2406-2407`). This is built by `_conversation_plan`
  (`1658-1727`), specifically `_current_conversation_step`
  (`2090-2094`): **the first step, in mission-defined order, whose
  `status == "pending"`.**
- Step status comes from `_mission_conversation_steps`
  (`1753-1866`), which branches on `mission.get("type")`.

## 2. The Deeper Root: `_mission_conversation_steps`'s `general_orientation` Branch

This is the single most important finding of this audit, and it sits one
layer below the two functions the sprint named -- but it is their direct,
load-bearing input, squarely within "todos sus callers."

For `auto_claim_guidance`, every step's status is **computed** from real
evidence: `_step_status_for_known_value(facts.get("injuries"),
slots.get("injuries"))` (`1766`), `_step_status_for_boolean_fact(facts.get(
"claim_report_loaded"))` (`1786`), etc. -- these check `SLOT_CLOSED_STATUSES`
or a non-null fact value and return `"completed"` once real evidence
exists (`_step_status_for_known_value`, `1899-1904`).

For the generic fallback branch -- `general_orientation`, and **any other
mission type that is not `auto_claim_guidance` or `knowledge_lookup`**
(`1853-1865`):

```python
if mission_type:
    return [
        _conversation_step(
            step_id="understand_user_need", step_type="clarification",
            label="comprender necesidad principal",
            status="pending",              # <- hardcoded, never computed
            mission=mission, slot="user_need",
            decision="response_prioritization", order=10,
        )
    ]
```

**`status="pending"` is a literal, hardcoded value.** It is never derived
from `slots.get("user_need")`, never checked against
`SLOT_CLOSED_STATUSES`, never re-evaluated at all. This single step is,
structurally, incapable of ever becoming anything other than the current
step for a `general_orientation` mission, for any number of turns, for any
input whatsoever -- accepted, rejected, or ignored. `_current_conversation_
step` will therefore select `"understand_user_need"` as `current_step`
every single turn after the first, and
`_should_reformulate_selected_question`'s `previous_current.slot == slot`
check (`2407`) will therefore be `True` every turn after the first,
**regardless of anything ACA-305D-RC2 does.**

This is why ACA-305D-RC2's confidence-gate fix -- correctly verified to stop
the wrong value from being written into the `user_need` slot -- could not
and did not change the response text: the plan never advances past this
one step, so the "same slot as last turn" trigger fires every time,
independent of whether last turn's answer was accepted, rejected, or never
attempted.

## 3. Answers to the Fourteen Questions

### 1. Conceptual responsibility

Deciding **how to phrase** a question the plan has already selected to ask
again, when the plan's own step-repetition signal says "this is the same
open question as last turn." It is a **presentation/wording** concern
layered on top of planning, not a planning or authority decision itself --
`_should_reformulate_selected_question` decides *whether to reword*;
`_reformulated_question_for_slot` decides *what words to use*. Neither
decides what to ask, when a mission ends, or what evidence to trust --
those remain, correctly, upstream (`_mission_conversation_steps`,
`MissionManager`).

### 2. Who holds authority over it

`ConversationState`, via `plan_conversational_response`, unchanged from the
existing field-ownership convention (this was never contested by ACA-305A/
B/C -- response planning was never claimed as `MissionManager` territory,
and this audit finds no reason it should be). The question is not who owns
it; it is what it consults.

### 3. Why it re-asks the same question even when the slot was rejected

Two independent, compounding reasons, both evidenced:

- (Primary, section 2) The `general_orientation` step's status is
  hardcoded `"pending"` and never advances, so "same slot as last turn" is
  always true after turn 1 -- rejection or absorption produce an identical
  planning signal, because the planning layer never distinguished them to
  begin with.
- (Secondary) `_should_reformulate_selected_question` itself only reads
  `conversation_plan` and `conversational_act` (`2397-2401`) -- it has no
  parameter, and no code path, that could consult whether the *reason* the
  slot is still open is "never answered" versus "answer explicitly
  rejected." Even if section 2's plan-advancement gap were fixed, this
  function would still be blind to *why* the slot is still pending.

### 4. Does it depend only on the slot name (`user_need`)?

**Yes, entirely**, for the wording. `_reformulated_question_for_slot`
(`2417-2437`) is a pure `if slot == "..."` chain: `injuries`, `user_role`,
`claim_report_loaded` (further branched only by `primary_need.key`, not by
mission), `documentation_available`, `user_need`. **`mission.get("type")`
is never read by this function at all.** The `user_need` branch returns a
single hardcoded, insurance-claim-specific string
(`"...el arreglo, la denuncia, la documentacion o los tiempos?"`)
unconditionally, for *every* mission type that reaches the generic
fallback step (today: `general_orientation`; structurally, any future
mission type not special-cased in `_mission_conversation_steps`).

### 5. Does it consult `resolve_pending_slot_answers`'s actual result?

**No.** Neither function receives the slot-resolution result, the
`slots` mapping, or the `derived_state["slot_resolution"]` trace (which,
since ACA-305D-RC2, now contains `resolutions` and `rejections`) as an
input. `_maybe_reformulate_required_question`'s parameters are `required`,
`selected`, `conversation_plan`, `primary_need`, `conversational_act` --
none of which carry this.

### 6. Does it consult `MissionTransitionDecision`?

**No.** `MissionTransitionDecision` lives in `CognitiveState.facts
["mission_transition_decision"]` (ACA-305D), populated by `MissionManager`
after this turn's mission evaluation. `plan_conversational_response` reads
`conversation_state.active_mission` (indirectly, via `_conversation_plan`'s
already-reprojected mission, section 1.2) but never reads the decision
record itself -- it cannot see *why* the mission is what it is, only *what*
it currently is.

### 7. Does it consult whether there was an explicit rejection?

**No** -- confirmed both by code inspection and empirically. ACA-305D-RC2's
`derived_state["slot_resolution"]["rejections"]` and the resulting
`mission_transition_proposals` entry are never read anywhere in this call
graph.

### 8. Does it consult whether there was a mission-change proposal?

**No.** No mission-transition-proposal data (`derived_state
["mission_transition_proposals"]`) is read by `plan_conversational_
response` or anything it calls.

### 9. What information does it currently ignore?

- Whether the previous turn's message was accepted, rejected, or produced
  no match at all (sections 5-8).
- The slot's own current `status`/`confidence`/`evidence` fields --
  `_should_reformulate_selected_question` never receives the `slots`
  mapping.
- `mission.type`, when choosing wording (section 4).
- Any `MissionTransitionDecision` or proposal evidence (sections 6-8).
- Turn count / repetition count beyond "was it the immediately preceding
  turn" -- a third consecutive ask of the same slot reformulates
  identically to the second (empirically confirmed: fixture 3's turn 3
  response is byte-identical to turn 2's).

### 10. Slot domain or mission domain?

**Structurally, it is written as slot-domain-only** (dispatch purely on
slot name), **but its content is mission-domain-specific** (the `user_need`
branch's wording assumes an insurance-claim conversation). This mismatch
-- slot-scoped dispatch, mission-scoped content -- is the direct mechanism
of section 4's cross-domain leakage. A correct design would keep dispatch
slot-scoped only if content is also genuinely slot-generic; here it is not.

### 11. Can it generate questions incompatible with the active mission?

**Yes, and it already does, today, for every `general_orientation`
conversation with a repeated `user_need` ask** -- confirmed by fixture 1/3's
empirical evidence (ACA-305D-RC2's diagnostic run): a
`general_orientation` mission (created for "Hola", nothing insurance-
related said) produces "...el arreglo, la denuncia, la documentacion o los
tiempos?" verbatim. This is not a hypothetical risk; it is the exact,
already-observed defect this whole sub-thread of ACA-305D exists to close.
It generalizes: any future mission type reaching the generic
`understand_user_need` step inherits the same wrong-domain text with zero
additional changes needed to reproduce it.

### 12. Can it hide correct decisions made by `MissionManager`?

**Plausible and structurally evidenced, not yet directly observed** (no
`replace`/`abandon`/`suspend` proposal is wired to fire in this exact
scenario yet, per ACA-305D-RC1). The mechanism the risk. `_should_
reformulate_selected_question` compares **slot names**, not mission
identity. If a future `replace` transition swapped `general_orientation`
for a *different* mission whose own first step also happens to use
`slot="user_need"` (plausible, since `user_need` is the generic fallback
slot for any unspecialized mission type), `previous_current.slot ==
slot` would still be `True` across the mission swap, and the reformulated
(and, per section 4, wrong-domain) question would appear immediately after
a `MissionManager` decision that was actually correct -- masking the
transition's effect from the user rather than reflecting it. This is a
real, load-bearing gap for any future work that wires `replace`, not an
already-observed failure today.

### 13. Which fixtures does this explain?

**Fixture 1 and fixture 3, exactly and completely**, for their response-
text assertions -- confirmed empirically in ACA-305D-RC2 (turn 2's and
turn 3's response text is produced by this mechanism verbatim; RC2's
diagnostic showed the confidence-gate fix correctly stopped state
absorption while this mechanism, untouched, kept producing the same
text). It also explains **fixture 4's turn-2 response text** (not asserted
by that fixture, but observed in RC2's diagnostic: "Recordas si alguna
persona resulto herida..." is `_reformulated_question_for_slot("injuries",
...)`'s hardcoded string) -- confirming the mechanism is general-purpose,
not `general_orientation`-specific, even though fixture 4's actual
assertions target mission-level state, not response text.

### 14. Which fixtures would still fail even after fixing this?

- **Fixture 4**, entirely -- its assertions check `active_mission.type`/
  `lifecycle_status` transition, which this mechanism has no bearing on
  (ACA-305D-RC1 already established fixture 4 needs an `abandonment_
  criteria` evidence path; nothing here changes that).
- **Fixture 3, possibly, even after a fix**, and this is worth stating
  plainly rather than assumed away: if the minimal fix (section 5) simply
  stops the wrong-domain reformulation and falls back to the *original,
  un-reformulated* question, turns 2 and 3 could still produce the
  **same** un-reformulated text (since section 2's plan-advancement gap
  means the same step is still selected both turns) -- satisfying "no
  wrong-domain content" but not necessarily fixture 3's literal
  `response3 != response2` bar. Whether that residual repetition is still
  a defect worth blocking on, once the wrong-domain content itself is
  fixed, is a decision for the next step (section 6), not settled here.

## 4. Effects Observable Beyond Response Text

- `evaluation.py:4052-4108` (`_count_reformulated_questions`,
  `_planned_question_was_reformulated`) treats reformulation as a tracked,
  named benchmark signal -- not merely incidental output. This is
  corroborating evidence for this audit's opening conclusion: reformulation
  was built as a **deliberate feature** (reword a repeated question rather
  than parrot it) with its own evaluation metric, not an accidental
  side-effect -- which is why "bug" is not the most accurate label, even
  though its current behavior, measured against ACA-305's now-established
  standards, is wrong for these four messages.
- `item["question_was_reformulated"]`, `item["reformulated_from"]`, and
  `item["reformulation_reason"]` (`2391-2393`) are already recorded on the
  `required_information` entry -- this is useful, existing observability
  this audit's recommendation (section 6) can build on rather than
  reinvent.

## 5. Architecture Recommendation

Directly answering the sprint's explicit question -- should reformulation
depend on pending slot / slot status / mission decision / both / another
component:

**Both slot status and mission-decision evidence, consumed by the existing
`ConversationState` planning layer -- not a new component, not a new
authority.**

Specifically:

1. **Slot status**: `_mission_conversation_steps`'s generic fallback branch
   (section 2) must compute `"understand_user_need"`'s status the same way
   `auto_claim_guidance`'s steps already do --
   `_step_status_for_known_value(confirmed_facts.get("user_need"), slots.
   get("user_need"))` -- rather than hardcoding `"pending"`. This is not a
   new mechanism; it is applying an existing, already-proven pattern
   (`_step_status_for_known_value`, already used four times in the
   `auto_claim_guidance` branch) to a branch that never received it. This
   alone does not change today's four-fixture behavior (a rejected match,
   per ACA-305D-RC2, correctly leaves the slot `PENDING`, so the step
   would still compute `"pending"` too) -- but it is a real, load-bearing
   correctness fix independent of this sprint's fixtures: it is what makes
   `_step_status_for_known_value` and `SLOT_CLOSED_STATUSES` (ACA-305D-RC1
   section 14's `answered` category) actually mean something for
   `general_orientation`, and it is a prerequisite for section 2's gap not
   silently persisting once a real answer *is* eventually given.
2. **Mission-decision evidence**: `_reformulated_question_for_slot`'s
   dispatch must stop being slot-name-only for content that is mission-
   specific. The minimal, most defensible form: pass `mission.get("type")`
   into the function and require it to match the domain the wording
   assumes (`auto_claim_guidance` for `injuries`/`user_role`/
   `claim_report_loaded`/`documentation_available`; nothing hardcoded for
   the generic `user_need` fallback) -- when the pairing does not match,
   return `""` (no reformulation), which `_maybe_reformulate_required_
   question` already correctly falls back from (`2388-2389`, unchanged).
   This does not require reading `MissionTransitionDecision` or proposal
   evidence directly; `mission.get("type")` is already available at the
   call site (`_conversation_plan`'s own `mission` variable, `1664`,
   already flows into `_selected_required_information` via `primary_need`/
   the mission dict itself is accessible through `conversation_state.
   active_mission`) and *is* the correct summary of whatever `MissionManager`
   most recently decided, without needing to re-derive or duplicate that
   decision.

**Why not "another component"**: routing this through a new evaluator or
through `MissionManager` itself would either (a) require `MissionManager`
to reach into response-composition concerns it has never owned and ACA-305A
explicitly kept it out of (wording is not mission lifecycle), or (b)
require inventing a second authority over response phrasing where
`ConversationState`'s planning layer already legitimately owns this. Both
violate the sprint's explicit "no introducir nuevas autoridades." The
fix belongs entirely inside functions `ConversationState` already owns,
consuming data (`slots`, `active_mission.type`) it already has in scope at
the point it currently ignores them.

**Why not the full `MissionTransitionDecision`/rejection-evidence
plumbing**: sufficient evidence for the fixtures at hand (section 13) is
already present in `mission.type` and `slots[slot].status` -- both
zero-new-plumbing reads. Threading `derived_state["slot_resolution"]
["rejections"]` or `mission_transition_proposals` into this function would
be a larger, cross-cutting change for no evidenced additional benefit
against the four fixtures, and risks exactly the kind of taxonomy
expansion ACA-305D-RC2 was explicitly told to avoid unless strictly
necessary. It is not necessary here.

## 6. Minimal Change to Close ACA-305D Without a New Authority

Two small, independently-verifiable edits, both inside functions
`ConversationState` already owns, neither creating a new authority or
consulted component:

1. `_mission_conversation_steps`'s generic fallback branch: compute
   `"understand_user_need"`'s status via the existing `_step_status_for_
   known_value` helper instead of a hardcoded `"pending"` literal.
2. `_reformulated_question_for_slot`: accept `mission_type` and return
   `""` (falling back to the existing, already-implemented un-reformulated
   question path) when the slot/mission pairing is not the one the
   hardcoded wording assumes, instead of returning insurance-specific text
   for any mission.

**What this would and would not close, stated plainly**: this is expected
to make fixture 1 pass (no wrong-domain content) and needs verification
for fixture 3 (section 3, question 14 -- may still show a repeated, but now
domain-correct, un-reformulated question; whether that residual repetition
still warrants failing fixture 3 is an open call). It would not touch
fixture 4 (needs the separate `abandonment_criteria` path ACA-305D-RC1
already identified) and would not touch fixture 2/5/6 (already green,
unaffected by this mechanism per section 1's call graph).

This document does not implement either edit. Per the sprint's
instruction, the exact wording of fixture 3's bar (must the *same*,
domain-correct question asked twice in a row still count as a defect, once
it is no longer wrong-domain?) is flagged as the one open decision worth
resolving explicitly before implementation, rather than assumed in either
direction.
