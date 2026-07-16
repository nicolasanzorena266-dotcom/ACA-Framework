# ACA-305C - Mission Lifecycle Benchmark and Integration Closure

Status: Conceptual design only. No code, class, or contract was created or
modified. No test was created or changed. No commit, no push.

Every claim about current code in this document was re-verified against the
working tree on 2026-07-16, in the same session that produced ACA-305A and
ACA-305B, with no repository changes in between other than the two prior
documents and `CURRENT_STATE.md`.

## 0. Objectives

1. Resolve the integration between mission lifecycle and `topic_stack`,
   closing every relationship the sprint brief lists as not allowed to stay
   open: `replace`, `abandon`, `suspend`, `resume`, active mission, active
   topic, suspended topics, navigation to a previous topic.
2. Define the permanent fixtures that must pass before and after
   implementation.
3. Close the exact acceptance criteria for ACA-305D.

`_advance_mission`'s future physical location remains an implementation
detail (per ACA-305B §20) and is not reopened here.

## 1. Current State Observed (Topic Stack, Fresh Evidence)

ACA-305A and ACA-305B audited `active_mission`. Neither fully audited
`topic_stack`'s own machinery. This section closes that gap with the same
rigor, because the sprint brief specifically requires it.

### 1.1 A mission-backed topic is a live projection of the mission, not an independent record

`_topic_from_current_state` (`conversation_state.py:4506-4544`) is called
by `update_topic_stack` every turn. When `conversation_state.active_mission`
has a `type`, it synthesizes a topic with a **derived, type-keyed id**:
`id = f"mission:{mission_type}"` (line 4510), `mission_type` and
`mission_goal` copied directly from the mission. There is no independent
topic identity for a mission beyond its `type`; the topic *is* a rendering
of the mission, recomputed fresh, not a separately authored record. Only
when no mission exists does a lighter `focus:{...}` topic get synthesized
from `conversation_state.focus` instead (lines 4526-4543), and only that
kind of topic — plus `unresolved_topic` entries created by `TOPIC_SHIFT`
handling (`_new_unresolved_topic`, lines 4547-4567) — represents something
genuinely independent of any mission.

### 1.2 `TopicStatus` already has the exact vocabulary `MissionLifecycleStatus` is missing a counterpart for

`TopicStatus` (`conversation_state.py:216-221`) declares five values:
`ACTIVE`, `SUSPENDED`, `RESUMED`, `COMPLETED`, `ABANDONED`. `TOPIC_LIFECYCLE`
(`conversation_state.py:239-245`) is a transition table structurally
identical in spirit to `MISSION_LIFECYCLE`:

```
ACTIVE    -> (SUSPENDED, COMPLETED, ABANDONED)
SUSPENDED -> (RESUMED, ABANDONED)
RESUMED   -> (ACTIVE, SUSPENDED, COMPLETED, ABANDONED)
COMPLETED -> ()
ABANDONED -> ()
```

Grep-verified: **`TopicStatus.COMPLETED` and `TopicStatus.ABANDONED` are
never assigned anywhere in `aca_os/`.** Every actual assignment in
`update_topic_stack` (`conversation_state.py:3330-3464`) uses only
`ACTIVE`, `SUSPENDED`, or `RESUMED`. This is the exact same pattern
ACA-305A §4.4 found for `MissionLifecycleStatus.COMPLETED`/`SUSPENDED` —
a fully declared, legally reachable, never-computed terminal state — except
here it is *more* complete than the mission side, since it already
distinguishes "completed" from "abandoned" as two separate terminal
outcomes, which is exactly the distinction ACA-305B had to introduce at
the `transition_type` level because `MissionLifecycleStatus` alone does
not carry it. **This document's integration decision reuses these two
existing, dormant topic states rather than inventing anything new.**

### 1.3 Topic navigation and mission lifecycle are today two independent mechanisms that happen to often move together, not one coordinated mechanism

`update_topic_stack` never reads or writes `active_mission`'s
`lifecycle_status`, never calls `MissionManager`, and is never called by
it. Tracing `_topic_refreshed_from_state`
(`conversation_state.py:4570-4583`), used every time a suspended topic is
resumed (`conversation_state.py:3368-3372`, `3386-3390`): if the resumed
topic's `mission_type` equals `conversation_state.active_mission`'s
current `type`, it re-synthesizes fully from the live mission (consistent
by luck, not by design). **If it does not match — i.e. the user resumes a
topic tied to a mission type different from whatever is currently
active — the function only refreshes the old topic's facts/slots/summary
and never touches `active_mission` at all.** Concretely: resuming a topic
today can leave `topic_stack` showing an active, `RESUMED` topic with
`mission_type = "auto_claim_guidance"` while `CognitiveState.active_mission.
type` is still `"general_orientation"` (or anything else) from before —
a real, reachable, evidenced divergence between what topic_stack believes
is being discussed and what `MissionManager` believes the mission is.
**This is the concrete mechanism behind the sprint brief's Q5
("¿reanudar un tópico implica necesariamente reanudar su misión?") — the
answer, in current code, is no, and that is the gap this document closes.**

### 1.4 The existing `mission_impact` signal currently asserts the opposite of the integration this sprint is deciding

`_mission_impact_for` (`conversation_state.py:4366-4381`), computed for
every conversational goal:

```python
"preserve_active_mission": strategy_name in {
    SIMPLIFY, SUMMARIZE, DEEPEN, CONTINUE, SWITCH_TOPIC,
    ASK_CLARIFICATION, REPAIR,
},
"may_change_mission_state": strategy_name in {REPAIR, CONTINUE},
```

`SWITCH_TOPIC` — the conversational strategy `_strategy_for_act` selects
specifically for the `TOPIC_SHIFT` act (`conversation_state.py:4253-4254`)
— is in the `preserve_active_mission` set and **absent** from the
`may_change_mission_state` set. In other words, the codebase's own
existing (write-only, per ACA-305A §4.3) signal currently declares that a
topic shift should *preserve* the mission, not change it — the opposite of
what ACA-304/ACA-305A's diagnosis calls for. Both fields are unconsumed
today (confirmed unchanged by grep in this session), so nothing currently
acts on this contradiction. But ACA-305B §14's eligibility rule
("goal/strategy-sourced evidence may only propose something other than
`maintain` when `may_change_mission_state == True`") would, if
implemented as written against today's `_mission_impact_for`, silently
block every `TOPIC_SHIFT`-driven mission proposal at the door. **This is a
required correction, not just new wiring**, and is treated as such in
§7 and §12 below — a one-line change to which set `SWITCH_TOPIC` belongs
to, not a restructuring of `ConversationState`.

### 1.5 `topic_stack` never deletes an entry

Every branch of `update_topic_stack` that calls `_remove_topic` does so
only to immediately re-`append` the same or an updated entry at the end of
the list (`conversation_state.py:3358-3359, 3373-3374, 3391-3392,
3414-3415`). There is no code path anywhere that drops a topic from the
stack outright. "Closing" a topic in this codebase's existing idiom means
changing its `status`, never removing the record. This directly answers
the sprint brief's Q4 in favor of "archive" over "eliminate" (§4).

### 1.6 A same-`type` mission created after a terminal topic would collide on id

Because a mission-backed topic's id is exactly `f"mission:{mission_type}"`
(§1.1) — one slot per *type*, not per mission instance — a mission of type
`auto_claim_guidance` that completes (topic `mission:auto_claim_guidance`
-> `COMPLETED`, terminal per `TOPIC_LIFECYCLE`) followed later by a *new*
`auto_claim_guidance` mission (via ordinary creation or `replace`) would
have `update_topic_stack`'s current-topic branch
(`conversation_state.py:3407-3417`) try to reactivate the same, now-
terminal, entry directly to `ACTIVE` — an illegal edge per
`TOPIC_LIFECYCLE[COMPLETED] = ()`. This is a real, evidenced integration
gap, not a hypothetical: it follows mechanically from the id scheme
already in the code. It is addressed as a required, narrowly-scoped fix
in §7/§12, not deferred as ambiguous.

## 2. Mission/Topic Integration Decision

### 2.1 Q1 — Same conceptual unit, or distinct?

**Mission is a specialization of topic.** Every mission has, at any given
turn, exactly one corresponding topic-stack entry
(`id = "mission:{type}"`), and that entry is a live projection of the
mission — not an independently authored fact (§1.1). For mission-backed
entries, mission and topic are the same conceptual unit viewed from two
angles: `active_mission` is the operational/task view (facts, slots,
`next_act`); the topic-stack entry is the conversational-navigation view
(priority relative to other topics, suspend/resume position, summary).
They are **not** two independent structures that happen to agree — this
document does not treat them as needing separate authorities as if they
were peers.

`topic_stack` is strictly broader than "missions": it also holds
`unresolved_topic` and `focus` entries that exist before, below, or
outside mission status (§1.1). Those remain entirely under
`ConversationState`'s existing ownership, untouched by this integration.

### 2.2 Q7 — Ownership per structure

Unchanged from the existing, already-declared field ownership
(`conversation_state.py:682-711`, ACA-305A §1.5, ACA-305B §13):

| Structure | Owner | Writer(s) |
| --- | --- | --- |
| `active_mission` | `MissionManager` | `MissionManager` only (ACA-305A §3, ACA-305B §13) |
| `topic_stack` | `ConversationState` | `ConversationState`'s `update_topic_stack` only |

This document does **not** merge these two ownerships and does **not**
grant either component `.evolve(...)`/write access to the other's field.
What it adds is a **synchronization contract**: evidence flows in both
directions (topic navigation evidence feeds mission proposals; accepted
mission decisions carry a topic-effect directive that `update_topic_stack`
applies), but each field is still written by exactly one owner, in the
same turn, in a fixed order (§2.5).

## 3. Cross-Transition Matrix

| Mission `transition_type` (ACA-305B §5) | Effect on the mission's own topic (`mission:{type}`) | Effect on the *previous* topic, if any | Evidence basis |
| --- | --- | --- | --- |
| `maintain` | Refreshed, stays/becomes `ACTIVE` | n/a | Already true today via `_topic_from_current_state`'s refresh (§1.1); no behavior change. |
| `complete` | -> `TopicStatus.COMPLETED` | n/a | New wiring. Legal edge already exists from `ACTIVE`/`RESUMED` (`TOPIC_LIFECYCLE`, §1.2). Entry is retained, not removed (§1.5) — its facts stay queryable by `memory_engine`/`context_manager` (ACA-305A §3 confirmed both already read `active_mission`; the topic-side record is their conversational-navigation counterpart). |
| `suspend` | -> `TopicStatus.SUSPENDED` | n/a | New wiring for *mission*-initiated suspension. Must reconcile, not duplicate, with topic-initiated suspension already performed by `TOPIC_SHIFT`/`new_topic` handling (`conversation_state.py:3353-3356`) — see idempotency rule §7.4. |
| `resume` | -> `TopicStatus.RESUMED` | n/a | New wiring closing the exact gap in §1.3: a mission `resume` decision must be accompanied by the corresponding topic transitioning to `RESUMED` in the same turn, not left for `update_topic_stack` to (possibly) do independently. |
| `replace` | Old topic (`mission:{old_type}`) -> `TopicStatus.SUSPENDED`; new topic (`mission:{new_type}`) created `ACTIVE` | Same entry as "old topic" column | Directly mirrors the existing `TOPIC_SHIFT`/`new_topic` behavior (`conversation_state.py:3353-3356`, which already suspends the active topic before creating a new one) — extended to be mission-type-aware rather than invented. |
| `abandon` | -> `TopicStatus.ABANDONED` | n/a | New wiring. Matches `abandon`'s "nothing to resume" semantics (ACA-305B §5) with the one existing topic status whose `TOPIC_LIFECYCLE` edge set is also empty (`ABANDONED -> ()`, §1.2) — a direct, not approximate, semantic match. |

Reverse direction — topic-originated evidence that must become a mission
proposal (ACA-305B §3.2's emitter list, extended):

| Topic-stack event (`update_topic_stack` outcome) | Mission proposal it must emit | `transition_type` |
| --- | --- | --- |
| `TOPIC_SHIFT`/`new_topic`: active topic suspended, new `unresolved_topic` created | If the suspended topic was mission-backed: propose suspending (or, once the new topic resolves to a mission `type`, replacing) the corresponding mission | `suspend` (immediately); `replace` (once the new topic's mission `type` is known, e.g. after the next classification-relevant turn) |
| `TOPIC_SHIFT`/`resume_previous` or `indirect_previous`: a suspended, mission-backed topic is resumed | Propose resuming the corresponding mission | `resume` |
| `CONTINUATION` resolving to a suspended, mission-backed topic | Same as above | `resume` |
| Ordinary current-topic refresh, mission-backed, no navigation event | Already covered by `_advance_mission`'s existing `maintain` emission (ACA-305B §14) | `maintain` |

## 4. Answers to the Ten Determination Questions

1. **Same unit or distinct?** Same conceptual unit for mission-backed
   topics; `topic_stack` is the broader structure (§2.1).
2. **Which mission transition produces which topic effect?** §3 (forward
   matrix).
3. **Does `replace` suspend, close, or preserve the previous topic?**
   **Suspends** — directly reusing the existing `TOPIC_SHIFT`/`new_topic`
   behavior (`conversation_state.py:3353-3356`) rather than inventing a
   new rule. The previous mission's facts/slots remain reachable via
   `resume` later, exactly like any other suspended topic.
4. **Does `abandon` delete, archive, or keep the topic?** **Archives** —
   `TopicStatus.ABANDONED`, entry retained in the stack (§1.5, §3). This
   codebase has no "delete a topic" idiom anywhere; inventing one here
   would be inconsistent with every other branch of `update_topic_stack`.
5. **Does resuming a topic necessarily resume its mission?** **Yes, once
   this integration is implemented** — this is the specific gap §1.3
   evidences in current code (it does not, today) and the specific gap
   this document closes: resuming a mission-backed topic must, in the
   same turn, produce an accepted `resume` mission decision. The converse
   also holds by invariant (§7.3): a mission `resume` must be accompanied
   by its topic becoming `RESUMED`.
6. **What happens when a mission ends but the topic stays relevant?** The
   topic is retained in a terminal status (`COMPLETED`/`ABANDONED`, never
   removed, §1.5) so it stays queryable as conversational history. Further
   engagement with that subject is modeled as a **new** mission (ordinary
   creation, or an explicit `replace`), never a resurrection of the
   terminal record — consistent with ACA-305B's own rule that mission
   `type` changes are always an explicit, distinct transition, never a
   silent mutation. §1.6's id-collision finding is the concrete mechanism
   this must account for; §7.5 states the required (narrow) fix.
7. **Which component owns which structure?** §2.2 — unchanged ownership,
   new synchronization contract, no merge.
8. **How is contradiction between `MissionManager` and topic logic
   avoided?** Fixed per-turn ordering plus idempotent, precedence-gated
   application — §7 (invariants) and §7.4 specifically.
9. **Cross invariants?** §7.
10. **What must be observable?** §8.

## 5. Correction Required Before Wiring (from §1.4)

`_mission_impact_for`'s `may_change_mission_state` set
(`conversation_state.py:4381`) currently excludes `SWITCH_TOPIC`, and its
`preserve_active_mission` set (line 4369-4378) currently includes it —
the opposite of what this integration requires. Before ACA-305D wires
`TOPIC_SHIFT`-sourced proposals (ACA-305B Stage 2), this single set
membership must be corrected: `SWITCH_TOPIC` moves into
`may_change_mission_state`'s eligible set. This is a one-line, narrowly
scoped correction to an already-existing, already-unconsumed function — it
does not add a field, does not change `ConversationState`'s shape, and is
not a restructuring. It is called out explicitly here because leaving it
unstated would let ACA-305D implement the wiring against a filter that
silently rejects the exact evidence it is supposed to accept.

## 6. Topic Id Disambiguation Requirement (from §1.6)

Before `complete`/`abandon` transitions are unlocked (ACA-305B Stage 3),
the topic-id derivation rule in `_topic_from_current_state`
(`conversation_state.py:4510`, currently `f"mission:{mission_type}"`) must
be extended so a terminal (`COMPLETED`/`ABANDONED`) topic is never
silently reactivated when a same-`type` mission is created afterward. The
exact id format (e.g. suffixing the terminal entry with its closing turn
before the new mission's fresh `mission:{type}` id is created) is left to
ACA-305D as an implementation mechanic — consistent with how ACA-305B
left `_advance_mission`'s physical location open — but the **requirement**
itself is not open: a terminal topic must never be the target of an
ordinary `ACTIVE`/`RESUMED` status write. This is restated as a hard
invariant in §7.2.

## 7. Cross Invariants

1. **Referential consistency.** At the end of any turn, every mission-
   backed topic-stack entry's `mission_type` must be consistent with a
   mission the system actually knows about: either it equals
   `active_mission.type` and its status is `ACTIVE`/`RESUMED`, or it
   refers to a historical mission and its status is
   `SUSPENDED`/`COMPLETED`/`ABANDONED`. A topic must never claim
   `mission_type = X` at `ACTIVE`/`RESUMED` status while
   `active_mission.type != X` (the exact divergence §1.3 evidences as
   currently reachable).
2. **No silent resurrection.** A topic in `COMPLETED` or `ABANDONED` is
   never transitioned back to `ACTIVE`/`RESUMED` by ordinary current-topic
   refresh (`update_topic_stack`'s ambient branches,
   `conversation_state.py:3407-3424`); reaching an equivalent state
   requires an explicit `replace` mission transition producing a **new**
   mission/topic pair, never a bare status flip on the same entry (§4,
   answer 6; §6).
3. **Resume is atomic across both structures.** A `resume` mission
   decision and its topic's transition to `RESUMED` occur in the same
   turn, or neither occurs. Equivalently: a topic navigating to
   `RESUMED` for a mission-backed entry whose mission is `SUSPENDED` must
   occur in the same turn as that mission's `resume` decision.
4. **One decision per field, per turn, idempotent on reapplication.**
   `MissionManager` never calls `.evolve(...)` on `topic_stack`;
   `update_topic_stack` never writes `active_mission`. When both a
   topic-side event (e.g. `TOPIC_SHIFT`/`new_topic` suspending the active
   topic) and a mission-side decision (e.g. `replace`, which per §3 also
   requires suspending the old topic) target the same topic entry in the
   same turn, applying the mission-side topic-effect directive after
   `update_topic_stack` has already run must be a no-op if the topic is
   already at the target status — never a second, redundant transition
   and never a contradiction. This reuses ACA-305B §10's idempotency
   convention (re-submitting an already-satisfied proposal is a legal
   no-op), applied here to the topic-effect side.
5. **Evidence flows one direction per turn; writes are ordered.** Within
   a turn: `update_topic_stack` computes topic navigation first (as it
   already does today, inside `ConversationManager.begin_turn`) and that
   output becomes *evidence* for mission proposals — it is never itself a
   mission decision. `MissionManager`'s decision, once accepted, is
   applied back onto `topic_stack` via a topic-effect directive that runs
   strictly after the mission decision is final. `update_topic_stack`
   must not re-decide anything based on a same-turn mission decision that
   has not been applied yet — this prevents the two mechanisms from
   racing or contradicting each other within one turn.
6. **No divergence window longer than one turn.** A mission transition's
   corresponding topic effect (§3) must be applied within the same turn
   the mission transition is accepted — never deferred to "whenever
   `update_topic_stack` next happens to touch that entry," which is
   exactly the mechanism that produces §1.3's evidenced divergence today.

## 8. Observability Requirements

Extends ACA-305B §21's `mission_decision` Introspection snapshot and the
existing `topic_stack_transition.v1` trace
(`conversation_state.py:3430-3448`) — both already exist as the natural
place for this, per each structure's own ownership (§2.2):

- Every accepted `MissionTransitionDecision` that has a topic effect
  (§3) carries a `topic_effect` sub-record: affected topic `id`,
  `from_status`, `to_status`, and `reason = "mirrors_mission_transition:
  {transition_type}"`.
- The existing `topic_stack_transition.v1` trace gains one additional,
  optional field, `triggered_by_mission_decision`, populated only when
  the topic transition was the topic-effect side of a mission decision
  (as opposed to an ordinary user-navigation-driven topic transition) —
  so the two traces are cross-referenceable in both directions without
  merging their contracts or changing either owner.
- Execution Trace's `_component_for_operation` map
  (`execution_trace.py:357-378`) must attribute the topic-effect
  application to `mission_manager` (it is a consequence of a mission
  decision) and ordinary topic navigation to `conversation_state`
  (unchanged) — these must remain distinguishable, not collapsed into one
  generic "topic changed" event, so an auditor can tell *why* a topic
  moved.
- All of this is additive to existing trace/snapshot shapes. It must not
  change any field's existing meaning — see §10 (byte-identical strategy).

## 9. Fixtures

Six permanent fixtures, as required by the sprint brief. Each is specified
completely enough to be implemented in ACA-305D without further design
decisions. All fixtures reproduce or extend the exact conversations already
used as evidence in ACA-304/ACA-305A.

### Fixture 1 — Greeting, then a social question

- **Initial state:** No prior turns. `active_mission = None`, `topic_stack
  = []`.
- **Message sequence:** `"Hola"`, then `"¿Cómo estás?"`.
- **Expected proposal (turn 2):** A `maintain`-type proposal for the
  `general_orientation` mission created in turn 1, evidence
  `evidence_kind = "conversational_act"` sourced from whatever act
  classification the second message receives — **not** a `pending_answer`
  interpretation of `"¿Cómo estás?"` as an answer to `user_need` (the
  ACA-304 failure this fixture targets, `conversation_state.py:5856-5867`'s
  `_looks_like_pending_answer`).
- **Expected decision:** Accepted `maintain`; mission stays
  `general_orientation`, `lifecycle_status` unchanged from `initialized`/
  `gathering_information`, `next_act` still `ask_user_need`.
- **Mission transition:** `maintain`.
- **Expected effect on `topic_stack`:** `mission:general_orientation`
  entry refreshed, stays `ACTIVE`. No suspension, no second topic created.
- **Minimum observable response:** Any response that does **not** contain
  the insurance-specific multi-choice reformulation ("el arreglo, la
  denuncia, la documentación o los tiempos") — that phrasing is only valid
  once an `auto_claim_guidance` mission exists, which it does not here.
- **Audit info:** `MissionTransitionDecision` for turn 2 present, showing
  `accepted = True`, `transition_type = "maintain"`, and — critically —
  showing the act actually used as evidence was *not* classified as
  `pending_answer` against `user_need`.
- **Prohibited behavior:** Treating `"¿Cómo estás?"` as an answer to the
  pending `user_need` question; emitting the `auto_claim_guidance`-specific
  reformulated question; creating or suggesting an `auto_claim_guidance`
  mission.

### Fixture 2 — General mission, natural topic change

- **Initial state:** Turn 1 `"Necesito ayuda"` already processed;
  `active_mission = {"type": "general_orientation", ...}`,
  `topic_stack = [{"id": "mission:general_orientation", "status": "active", ...}]`.
- **Message:** `"Mis vacaciones"`.
- **Expected proposal:** A `replace` (or, at minimum, `abandon`) proposal
  from the abandonment-criteria/topic-relevance evidence path (ACA-305B
  §3.2, §14), evidence `evidence_kind = "abandonment_criterion"` or
  `"conversational_act"` (`TOPIC_SHIFT`, if detection quality — ACA-304
  Option 2 — has been improved enough by then to recognize this as
  off-topic; this fixture does **not** require that separately-scoped
  detection work to be complete to be meaningful, see §10). No requirement
  that the user say "cambiemos de tema" verbatim — that lexical
  requirement is exactly what ACA-304 found insufficient and this fixture
  exists to not reintroduce.
- **Expected decision:** Accepted `replace` (target type: whatever
  classification "Mis vacaciones" would receive under ordinary mission
  creation rules, most likely a new `general_orientation` instance around
  a different `user_need`, or an explicit "off-topic" mission type if one
  is later introduced — out of scope for this document to invent) **or**,
  if evidence is judged insufficient for `replace`'s higher confidence
  threshold (ACA-305B §7: 0.85), an accepted `maintain` that at minimum
  does **not** repeat the exact same reformulated question — either
  outcome is acceptable for this fixture as long as the mission is not
  left byte-identical to before turn 2.
- **Mission transition:** `replace` (preferred) or `maintain` with visibly
  different `next_act`/evidence (minimum acceptable).
- **Expected effect on `topic_stack`:** If `replace`: old topic
  `mission:general_orientation` -> `SUSPENDED`; new topic created `ACTIVE`
  (§3). If `maintain`: no topic-stack change beyond the ordinary refresh.
- **Minimum observable response:** Must not be the byte-identical
  repeated question from ACA-304's reproduction.
- **Audit info:** `MissionTransitionDecision` for this turn must be
  present and must **not** be a rejected `maintain` with
  `rejection_reason` empty (i.e., something must have been evaluated,
  even if ultimately only `maintain` was accepted).
- **Prohibited behavior:** Repeating the exact same question verbatim
  after this turn; requiring the literal phrase "cambiemos de tema" to
  produce any transition at all.

### Fixture 3 — Explicit rejection of the offered options

- **Initial state:** `active_mission = {"type": "auto_claim_guidance", ...}`,
  last response was the multiple-choice reformulation ("¿arreglo, la
  denuncia, la documentación o los tiempos?"), `next_act = "ask_user_need"`
  or equivalent.
- **Message:** `"Ninguno"`.
- **Expected proposal:** At minimum, evidence that `"ninguno"` is
  recognized as declining the *offered options*, not as a slot value of
  `"none"` for `user_need` — this requires `_is_minimal_affirmation_or_
  negation` (`conversation_state.py:5887-5894`) to be extended to
  recognize `"ninguno"` as a negation (it currently is not in the
  `{"no", "nop", "para nada", "negativo"}` set), which is a detection
  precision fix, not a mission-authority fix — noted here because this
  fixture cannot pass without it, but the fix itself belongs to whichever
  component owns `_is_minimal_affirmation_or_negation`, not to this
  document's mission/topic contract.
- **Expected decision:** Either an accepted `maintain` that produces a
  **different** `next_act` (e.g. asking an open question instead of
  repeating the closed multiple-choice one) or an accepted `abandon`/
  `replace` if corroborating evidence (§ACA-305B §9 step 4) is present.
- **Mission transition:** `maintain` (with a changed `next_act`) at
  minimum; `abandon`/`replace` acceptable if evidenced.
- **Expected effect on `topic_stack`:** Refreshed in place if `maintain`;
  per §3 if `abandon`/`replace`.
- **Minimum observable response:** Must not be the identical multiple-
  choice question repeated verbatim.
- **Audit info:** Decision trace showing the evidence that `"ninguno"` was
  not treated as a `user_need` slot value.
- **Prohibited behavior:** Repeating the identical question; storing
  `"ninguno"` as the confirmed value of `user_need`.

### Fixture 4 — Completely unrelated question

- **Initial state:** Same as Fixture 3, but the message is unrelated
  rather than a rejection of the options.
- **Message:** `"¿Dios existe?"`.
- **Expected proposal:** `abandon` or `replace`, evidenced by
  `abandonment_criterion` and/or `TOPIC_SHIFT` (once detection quality
  work lands — see the same caveat as Fixture 2). Confidence must meet
  the higher threshold ACA-305B §7 assigns these transition types (0.85)
  — this fixture is the canonical test of whether that threshold, once
  tuned, is reachable by realistic evidence for a clearly off-topic
  message, or whether the threshold itself needs revisiting in 305D.
- **Expected decision:** Accepted `abandon` (mission becomes `None`,
  nothing left to resume, matching ACA-305B §5's rationale that a
  completely unrelated question has no natural "suspend and resume"
  shape) **or** accepted `replace` if the off-topic message is judged to
  itself be a plausible new mission target (unlikely for this specific
  message, but the fixture should assert whichever the implementation
  actually produces is internally consistent — not assert one over the
  other in advance).
- **Mission transition:** `abandon` (preferred reading of "completely
  unrelated") or `replace`.
- **Expected effect on `topic_stack`:** `abandon` -> old topic
  `mission:auto_claim_guidance` -> `TopicStatus.ABANDONED` (§3). `replace`
  -> old topic -> `SUSPENDED`, new topic created.
- **Minimum observable response:** Must not be the identical multiple-
  choice question repeated verbatim; ideally acknowledges the question is
  unrelated to the insurance matter without inventing an answer to it
  (response *content* quality is explicitly not what this fixture grades
  — only that the mission/topic state actually changed).
- **Audit info:** Decision trace with `rejection_reason = ""`,
  `accepted = True`, and — if `abandon` — `active_mission = None`
  confirmed in the same turn's `mission_before`/`mission_after` pair.
- **Prohibited behavior:** Repeating the identical question; leaving
  `active_mission` byte-identical to before this turn; silently treating
  the question as a new slot value for anything insurance-related.

### Fixture 5 — Byte-identical continuation of `auto_claim_guidance`

- **Initial state:** An `auto_claim_guidance` mission with some slots
  already answered (e.g. `injuries` confirmed `False`), `missing =
  ["user_role"]`.
- **Message:** A valid, on-topic answer to the pending slot (e.g.
  `"Soy el conductor"`).
- **Expected proposal:** `maintain`, sourced from `_advance_mission`
  (migrated per ACA-305B §16.2 Stage 1 to emit a proposal instead of being
  adopted by equality check), evidence `evidence_kind = "fact_slot_delta"`,
  confidence `1.0` (§ACA-305B §7).
- **Expected decision:** Accepted `maintain`.
- **Mission transition:** `maintain`.
- **Expected effect on `topic_stack`:** Refreshed in place, `ACTIVE`,
  identical to today's behavior.
- **Minimum observable response:** Byte-identical to what the system
  produces today for this exact scripted sequence, prior to any
  ACA-305C/D change.
- **Audit info:** New in this migration: an accepted
  `MissionTransitionDecision` trace exists where none did before (today,
  per ACA-305B §10, `_advance_mission` returning an unchanged mission
  produces no trace at all when nothing changed — but *this* fixture
  changes a slot, so today's system already produces a
  `mission_advancement` trace; the acceptance bar is that the new trace's
  `mission_after` field is byte-identical to today's `mission_advancement.
  mission_after`, not that a trace newly appears).
- **Prohibited behavior:** Any difference in `active_mission`'s resulting
  content, `next_act`, `progress`, or `lifecycle_status` compared to
  today's system for this exact scripted input. This is the fixture the
  byte-identical comparison strategy (§10) is built around.

### Fixture 6 — Topic change and return

- **Initial state:** Mission A (`auto_claim_guidance`) active, one topic
  `mission:auto_claim_guidance` `ACTIVE`.
- **Message sequence:** A message that shifts to an unrelated subject B
  (e.g. `"Cambiemos de tema, contame de mis vacaciones"` — uses the
  explicit lexical trigger deliberately, unlike Fixtures 2/4, specifically
  to isolate topic-resume/mission-resume integration from the separately-
  scoped detection-quality problem), followed later by `"volvamos a la
  denuncia"`.
- **Expected proposal (shift turn):** `suspend` (or `replace`, per §3's
  forward matrix for `TOPIC_SHIFT`/`new_topic`) for mission A.
- **Expected proposal (return turn):** `resume` for mission A, evidenced
  by `TOPIC_SHIFT`/`resume_previous` direction (`_topic_navigation_
  direction`, `conversation_state.py:4481-4497`, already matches
  `"volvamos"`/`"la denuncia"`) resolving to the suspended
  `mission:auto_claim_guidance` topic via `_resolve_topic_reference`
  (`conversation_state.py:4598-...`, already scores `denuncia_reference`
  and `active_mission_match` highly).
- **Expected decision (shift turn):** Accepted `suspend` (or `replace`);
  mission A's `lifecycle_status` -> `SUSPENDED`.
- **Expected decision (return turn):** Accepted `resume`; mission A's
  `lifecycle_status` returns to `GATHERING_INFORMATION` or `WAITING_USER`
  per §ACA-305B §6, **with its previously-collected facts/slots intact**
  — not a fresh mission.
- **Mission transition:** `suspend` then `resume`.
- **Expected effect on `topic_stack`:** Shift turn: `mission:auto_claim_
  guidance` -> `SUSPENDED`, new topic for subject B created `ACTIVE`.
  Return turn: subject-B topic -> `SUSPENDED` (or left as-is, per whatever
  the ordinary `TOPIC_SHIFT` handling already does when a new active topic
  is chosen), `mission:auto_claim_guidance` -> `RESUMED`, **and — the
  specific integration this fixture proves — this happens in the same
  turn as the mission's `resume` decision, not a turn later** (§7.3, §7.6).
- **Minimum observable response:** References the previously-collected
  facts (e.g. does not re-ask `user_role` if it was already answered
  before the shift).
- **Audit info:** Both turns' `MissionTransitionDecision`s present;
  return turn's `topic_effect` sub-record (§8) cross-references the same
  turn's mission decision.
- **Prohibited behavior:** Resuming the topic without resuming the
  mission (today's actual behavior, §1.3 — this fixture is the direct
  regression test for that gap); creating a brand-new
  `auto_claim_guidance` mission instead of reactivating the suspended one;
  losing previously-confirmed facts/slots across the suspend/resume cycle.

## 10. Byte-Identical Comparison Strategy

Directly extends ACA-305B §16.2 Stage 1's acceptance bar
("byte-identical `active_mission` output... across the existing test suite
and benchmarks") to also cover `topic_stack`, since this document adds a
second field whose values must not silently change for already-working
paths.

1. **Baseline capture.** Before any ACA-305D change, run the existing test
   suite (730/730 per ACA-303) and the existing benchmark corpora
   (`benchmarks/conversations/`, `benchmarks/semantic/`,
   `benchmarks/verbalization/`) and, for every turn of every scripted
   conversation already covered, snapshot `active_mission` and
   `topic_stack` as canonical JSON (sorted keys, stable float formatting)
   into a baseline artifact. This baseline is captured once, from the
   current working tree, before ACA-305D touches anything.
2. **Field classification.** Every field in both structures is classified
   as either **decision-relevant** (anything that already exists today:
   `type`, `status`, `lifecycle_status`, `progress`, `next_act`,
   `blockers`, `missing`, `slots`, `facts` for missions; `id`, `type`,
   `mission_type`, `mission_goal`, `status`, `priority`,
   `associated_facts`, `associated_slots`, `summary`,
   `created_turn`/`last_active_turn` for topics) or **additive/
   observability-only** (anything this document or ACA-305B introduces
   purely for audit purposes, e.g. `triggered_by_mission_decision`).
3. **Regression rule.** After ACA-305D's Stage 1 (the migration stage
   ACA-305B §16.2 scopes as behavior-preserving), re-run the same suite
   and corpora and diff snapshots turn-by-turn. **Any difference in a
   decision-relevant field is a regression**, full stop, regardless of
   whether the new code path is "more correct" — Stage 1 is scoped
   exactly to not change behavior, only authority (ACA-305A §7, ACA-305B
   §16.2 point 2). Differences confined to additive/observability fields
   are expected and acceptable.
4. **Divergence is expected, and required, starting at Stage 2/3.** Once
   ACA-305D reaches the stages that actually wire new signals
   (`TOPIC_SHIFT`, `abandonment_criteria`, `mission_impact`) or unlock new
   transition types, decision-relevant divergence from the Stage-1
   baseline is expected for the specific fixtures designed to exercise
   those signals (Fixtures 2, 4, 6) — the byte-identical bar at that point
   applies only to fixtures/scenarios *not* related to the newly-wired
   signal (e.g. Fixture 5 must still be byte-identical against the Stage-1
   baseline even after Stage 3 ships; Fixture 1's absence of an
   `auto_claim_guidance` reformulation must hold at every stage).
5. **Comparison artifact ownership.** The baseline and diff tooling
   themselves are an ACA-305D implementation task (out of scope to build
   here, per the "no code" constraint) — this section specifies the
   method and the pass/fail rule, not the script.

## 11. Risks

| Risk | Description | Mitigation |
| --- | --- | --- |
| §5's correction is skipped | If `_mission_impact_for`'s set membership fix is treated as optional cleanup rather than a blocking prerequisite, Stage 2 wiring silently produces zero `SWITCH_TOPIC`-sourced proposals, and the implementation would appear to "not find a bug" when it is actually blocked at the eligibility filter. | Stated as a required, ordered prerequisite in §5 and reflected in the ACA-305D plan (§12) as its own numbered step, not folded silently into "wiring." |
| §6's id collision is deferred past when it matters | If ACA-305D unlocks `complete`/`abandon` (Stage 3) before addressing the topic-id disambiguation requirement, the very first same-type mission reuse after a completed/abandoned mission would attempt an illegal `TOPIC_LIFECYCLE` edge. | §7.2 restates this as a hard invariant, and §12's plan places the id-disambiguation mechanic before Stage 3, not concurrent with or after it. |
| Confidence thresholds (ACA-305B §7) are untested against real off-topic phrasing | Fixtures 2 and 4 depend on detection quality (ACA-304 Option 2) that is explicitly out of scope for the mission/topic authority work. | Both fixtures are written to accept either a full `replace`/`abandon` outcome or, at minimum, a `maintain` that visibly changes `next_act` — so they remain meaningful acceptance tests even before detection-quality work lands, rather than being blocked on it (§9, Fixtures 2 and 4). |
| Topic-effect application and ordinary topic navigation race within a turn | §7.5's ordering rule (topic navigation first, mission decision second, topic-effect application third) is a new sequencing constraint on `ConversationManager.begin_turn`'s existing call order (`assimilate_user_facts` at line 205, `update_topic_stack` at line 206, per ACA-305A §1.3's trace). | Restated explicitly as invariant §7.5 so ACA-305D cannot implement the topic-effect application as a race with, rather than a strict successor to, `update_topic_stack`. |
| `resume` atomicity (§7.3) is violated by a partial implementation | If ACA-305D implements mission-side `resume` before topic-side `RESUMED` wiring (or vice versa), Fixture 6 would fail in a way that looks like a detection problem rather than an atomicity problem. | Fixture 6 is written specifically to isolate this (§9) using the explicit lexical trigger, removing detection-quality as a confound. |

## 12. Exact Implementation Plan for ACA-305D

Ordered; each step's acceptance bar must pass before the next begins,
consistent with ACA-305B §16.2's staged migration and this document's
byte-identical strategy (§10):

1. **Prerequisite correction.** Fix `_mission_impact_for`'s
   `may_change_mission_state` set to include `SWITCH_TOPIC` (§5). Run the
   existing test suite; this alone must be byte-identical everywhere
   except the (currently unconsumed) `mission_impact` field's own value,
   since nothing reads it yet.
2. **Stage 1 (ACA-305B, unchanged scope).** Gate the `auto_claim_guidance`
   `maintain` path through `MissionManager`'s new decision procedure,
   replacing `MISSION_LOAD_FROM_CONVERSATION_STATE`'s equality-check
   adoption. Capture the Stage-1 baseline (§10 step 1) immediately before
   this step, diff immediately after. Fixture 5 is the acceptance test.
3. **Topic-effect application, scoped to `maintain` only.** Wire the
   trivial case first: an accepted `maintain` decision's topic-effect
   directive (refresh, stay `ACTIVE`) applied after `update_topic_stack`,
   confirmed idempotent against what `update_topic_stack` already
   produced that turn (§7.4). This is intentionally a no-op-shaped step —
   its only purpose is proving the ordering/idempotency plumbing (§7.5)
   before any transition type that actually changes a topic's status is
   introduced.
4. **`suspend`/`resume` wiring, evidenced by existing `TOPIC_SHIFT`
   handling only** (not new detection). Implement the forward matrix's
   `suspend`/`resume` rows (§3) and the reverse-direction table's
   `resume_previous`/`indirect_previous` rows, using `TOPIC_SHIFT` acts
   exactly as currently detected (no lexical-whitelist changes). Fixture 6
   is the acceptance test — deliberately using an explicit lexical trigger
   so this step is not confounded by detection-quality work.
5. **Topic id disambiguation.** Implement the narrow fix required by §6
   before proceeding — a terminal topic must never be reactivated by a
   same-type mission's ordinary creation/refresh path.
6. **`complete` wiring**, evidenced by `_advance_mission`'s existing
   `auto_claim_guidance` fact/slot logic reaching a state where no slots
   are missing and the relevant facts are confirmed (§ACA-305B §6's
   `_mission_status_for` already has the missing branch identified —
   ACA-305A §4.4 — this step is where it finally gets a caller).
7. **`replace`/`abandon` wiring, evidenced by `abandonment_criteria`
   evaluation.** Implement the abandonment-criteria evaluator ACA-305B
   §14 specifies, and the forward matrix's `replace`/`abandon` rows.
   Fixtures 2 and 4 are the acceptance tests, understanding (§11) that
   full success on the *response content* of those fixtures also depends
   on separately-scoped detection-quality work (ACA-304 Option 2).
8. **Fixture 1 and Fixture 3 verification.** These do not require new
   mission-transition machinery on their own (Fixture 1 requires only
   that `pending_answer` misclassification not occur; Fixture 3 requires
   only the `_is_minimal_affirmation_or_negation` extension noted in §9)
   — verify them once steps 2-3 land, and again after step 7, to confirm
   neither regresses.
9. **Observability (§8).** Implemented alongside steps 2-7, not after —
   per ACA-305B's own precedent (its §21/acceptance criteria required
   this, not deferred it) and this document's risk table (§11,
   observability-lag risk).

## 13. Explicitly Out of Scope

- Any code, class, dataclass, or contract implementation.
- Any test creation or modification.
- Improving topic/relevance **detection** quality (ACA-304 Option 2) — the
  lexical narrowness of `_mentions_topic_shift`/`SemanticAuthority`'s own
  topic-shift markers remains a separately-sequenced Semantic Firewall
  item. Fixtures 2 and 4 are written to remain meaningful without it
  (§11).
- The exact topic-id disambiguation format (§6) — requirement only,
  format left to ACA-305D.
- `_advance_mission`'s physical code location — remains open per
  ACA-305B §20, not reopened here.
- Reopening `semantic_authority_pilot.py`'s promotion scope.
- Tuning the confidence thresholds ACA-305B §7 proposed — Fixtures 2 and
  4 are explicitly designed to be the tuning inputs for ACA-305D, not to
  pre-decide the final numbers here.
- Any change to `PublicConversationProductLayer.reset()`.
- Any change to the LLM Verbalization / Conversational-First output
  layer, confirmed again this session to have no mission- or
  topic-authority surface.
- Building the byte-identical comparison tooling itself (§10 specifies
  method and rule, not a script).

`CURRENT_STATE.md` is updated separately, reflecting that the
mission/topic integration decision and the ACA-305D acceptance criteria
are both fully closed, with no relationship from the sprint brief's
required list (`replace`, `abandon`, `suspend`, `resume`, active mission,
active topic, suspended topics, navigation to a previous topic) left
ambiguous. The two items explicitly still open (§6's exact id format,
`_advance_mission`'s physical location) are implementation mechanics, not
authority or integration questions, and do not block ACA-305D.
