# ACA-305 - Mission Lifecycle Authority Architecture Decision (ACA-305A)

Status: Architecture decision. No code, contract, or class was created or
modified. Every claim below was re-verified against the current working
tree (including uncommitted changes) on 2026-07-16, not re-derived from
ACA-304 or from chat history.

Scope: Answer, with code-level evidence, which component has authority to
maintain, complete, suspend, replace or abandon the active mission, and
under what evidence and invariants. Produce a recommended decision. Do not
implement it.

Relationship to ACA-304: ACA-304 is confirmed accurate on its central claim
(no component reevaluates a mission after creation) but its code excerpt of
`MissionManager.before_kernel` was abbreviated. Current code is more
sophisticated than that excerpt suggests, and that extra sophistication
changes the shape of the recommended decision. Section 1.3 documents the
correction precisely.

## 1. Current State Observed

### 1.1 Where a mission is created

`MissionManager.before_kernel` (`aca_os/mission_manager.py:8-69`) is the only
call site anywhere in `aca_os/` that evolves `CognitiveState` with operation
`MISSION_CREATE`. Classification is keyword matching on the raw first
message (`me chocaron`, `choque`, `accidente`, `siniestro`, `denuncia` ->
`auto_claim_guidance`; zero-cost flow `knowledge_lookup` ->
`knowledge_lookup`; otherwise `general_orientation`). This part of ACA-304's
finding is unchanged and still accurate.

### 1.2 Where a mission is invoked per turn

`MissionManager.before_kernel` is called once per turn
(`aca_os/runtime.py:588-592`), and `MissionManager.after_kernel` is also
called once per turn, inside `MemoryStepHandler.execute`
(`aca_os/step_handlers.py:253-256`). **The component is invoked every turn.**
ACA-304's framing ("it only fires once") describes the *classification
logic's* effective behavior, not the invocation cadence. This distinction
matters for the decision below: the wiring point already exists on every
turn; what is missing is what `before_kernel` does with it.

### 1.3 Correction to ACA-304: a second, narrower mission-advancement path already exists and is wired

ACA-304 quoted only `mission_manager.py:16-22`. The full current method
(`aca_os/mission_manager.py:15-27`) is:

```
current = state or CognitiveState()
if current.active_mission:
    if conversation_state is not None and conversation_state.active_mission == current.active_mission:
        return current.evolve("MISSION_LOAD_FROM_CONVERSATION_STATE", active_mission=dict(current.active_mission))
    return current
if conversation_state is not None and conversation_state.active_mission:
    return current.evolve("MISSION_LOAD_FROM_CONVERSATION_STATE", active_mission=dict(conversation_state.active_mission))
...
```

This is not a no-op. Tracing the full per-turn call chain:

1. `ConversationManager.begin_turn` (`aca_os/conversation_manager.py:127-246`)
   calls `initial.assimilate_user_facts(event.payload)`
   (`conversation_manager.py:205`), which internally calls
   `_advance_mission` (`aca_os/conversation_state.py:5483-5530`, invoked at
   `conversation_state.py:4931-4937`).
2. `_advance_mission` recomputes `lifecycle_status`, `next_act`, `progress`,
   `blockers`, `missing`, `slots` and a `facts` snapshot for the mission,
   using a real 7-state machine (`MissionLifecycleStatus`,
   `conversation_state.py:65-73`, transition table `MISSION_LIFECYCLE`,
   `conversation_state.py:86-122`) — **but only when
   `active_mission.get("type") == "auto_claim_guidance"`**
   (`conversation_state.py:5489`). For any other mission type (including
   `general_orientation`, the type used in every turn of the ACA-304
   reproduction) this function returns `None` immediately and nothing
   advances.
3. `begin_turn` then calls `initial.to_cognitive_state(base=state, ...)`
   (`conversation_manager.py:246`), whose implementation sets
   `data["active_mission"] = deepcopy(self.active_mission)`
   (`conversation_state.py:553`) — i.e. the CognitiveState handed to the
   rest of the turn already carries `ConversationState`'s advanced mission,
   not the prior turn's frozen copy.
4. Back in `ACAOSRuntime.process`, this CognitiveState becomes
   `with_decision_graph`, which is passed as `current` into
   `MissionManager.before_kernel` (`runtime.py:588-592`), alongside
   `conversation_state=operational_conversation_state` (the same advanced
   `ConversationState`). Because both were derived from the same
   `assimilate_user_facts` call, `conversation_state.active_mission ==
   current.active_mission` holds, so `before_kernel` takes the
   `MISSION_LOAD_FROM_CONVERSATION_STATE` branch and **adopts the
   advancement unconditionally** — it does not evaluate it, gate it, or
   check confidence; equality is the only check performed.
5. `runtime.py:593-596` then reprojects `operational_conversation_state`
   from this same (now-adopted) CognitiveState via
   `project_from_cognitive_state`, which is consistent because step 4
   already synchronized them.

**Conclusion:** for `auto_claim_guidance` missions, fact/slot-driven
advancement (including a full lifecycle-status state machine with
`waiting_user`, `gathering_information`, `ready_to_progress`,
`progressing`, `completed`, `suspended`) already exists, is already wired
end-to-end, and already runs every turn. It is real, not aspirational. Two
things are still true and unchanged from ACA-304 despite this:

- It is scoped to exactly one mission type. `general_orientation` (the type
  that failed in the reproduced conversation) never enters this path.
- It never changes `type`, never proposes replacement or abandonment, and
  — see §4.4 — the `completed`/`suspended` states it declares are legal
  transition targets that **no code ever actually produces**, so they are
  reachable in the state table but dead in practice.

### 1.4 A second decision site, not a second writer of the final field

`_advance_mission` computes the mission delta; it lives in
`conversation_state.py` and is invoked from `ConversationManager.begin_turn`
— i.e., **before** `MissionManager` runs for that turn. `MissionManager`
does not independently decide anything in this path; it adopts
whatever `ConversationState` already computed, gated only by an equality
check against its own prior value. `CognitiveState.active_mission` still
has exactly one write path (`MissionManager.before_kernel`/`after_kernel`
via `.evolve(...)`), so there is no literal duplicate-writer bug of the
kind ACA-104/FW-11 fixed. But there are, today, **two decision sites**
computing what the mission should become — `_advance_mission` (fact/slot
driven, `conversation_state.py`) and `MissionManager` (creation and
progress-only bump, `mission_manager.py`) — reconciled by a bare equality
check rather than an explicit authority contract. This is evidence the ADR
decision must address directly (§5, §7).

### 1.5 The declared field-ownership metadata is aspirational, not descriptive, on this point

`aca_os/conversation_state.py:702-711` declares:

```
"active_mission": ConversationFieldOwnership(
    ..., owner="mission_manager", writers=("mission_manager",),
    rationale="Mission remains the runtime task object but is projected into conversation state.",
),
```

and `aca_os/authority_dependency_graph.py:263` declares the `mission` node
as `PRIMARY_AUTHORITY`, owner `mission_manager`, with rationale
"MissionManager must consume semantics but retain mission authority." Both
of these are intent declarations already checked into the architecture
tooling, not enforcement. §1.3-1.4 show the intent ("MissionManager
retains authority") is not fully what happens in practice for
`auto_claim_guidance` today (`ConversationState` computes the content,
`MissionManager` rubber-stamps it). This is useful evidence about where the
project already *wants* to end up, but it cannot be trusted as a
description of current behavior without the trace in §1.3 to back it up —
consistent with HANDOFF.md's instruction not to trust documentation over
verified callers.

## 2. Authority Map (Current, Verified)

| Question | Answer, with evidence |
| --- | --- |
| Who creates a mission | `MissionManager.before_kernel`, `mission_manager.py:28-69`. Sole `MISSION_CREATE` call site in the repository. |
| Who advances mission content turn-to-turn | For `auto_claim_guidance`: `_advance_mission` (`conversation_state.py:5483-5530`), invoked from `ConversationState.assimilate_user_facts`, adopted unconditionally by `MissionManager` via equality check (§1.3). For every other mission type, including `general_orientation`: nobody. `after_kernel` (`mission_manager.py:71-82`) only ever raises `progress` to at least `0.75` when a response exists; it does not touch `lifecycle_status`, `next_act`, `blockers`, or `missing`. |
| Who can change mission `type` mid-conversation | Nobody. No call site anywhere sets `active_mission["type"]` after `MISSION_CREATE`. |
| Who can complete a mission | Nobody, in the live path. `MissionLifecycleStatus.COMPLETED` is a declared legal transition target (`MISSION_LIFECYCLE`, `conversation_state.py:102,108,117`) and is *read* by `_legacy_mission_status` (`conversation_state.py:5575-5580`), but `_mission_status_for` (`conversation_state.py:5533-5542`), the only function that computes a target status, never returns `COMPLETED`. Dead transition target (§4.4). |
| Who can suspend a mission | Same as above: `SUSPENDED` is a legal table entry and a legacy-status output value, never a computed target. Dead transition target. |
| Who can replace a mission with a different one | Nobody, organically. The only mission-clearing path in the repository is `PublicConversationProductLayer.reset()` (`public_conversation_product_layer.py:426-428`), reachable only via an explicit `public_action_id == "reset_conversation"` UI action (`public_conversation_product_layer.py:1673-1674`) — a manual "start over" control in the public/legacy adapter layer, outside `ConversationState`/`MissionManager`. |
| Who decides the conversation changed topic | `_mentions_topic_shift` (Legacy, lexical whitelist) and `SemanticAuthority`'s own, differently-worded lexical list. Both produce a `TOPIC_SHIFT` conversational act (`ConversationalActType.TOPIC_SHIFT`, priority 86, `conversation_state.py:4157`) that only ever mutates `topic_stack` (`update_topic_stack`, `conversation_state.py:3353-3362`). It has no call site that reads or writes `active_mission`. Confirmed unchanged from ACA-304 by direct grep of every `TOPIC_SHIFT` reference in `aca_os/` (§4.1). |
| Who evaluates declared abandonment criteria | Nobody. `_abandonment_criteria_for` (`conversation_state.py:4321`) writes a list (e.g. `"new_unrelated_topic_detected"`) into `conversational_goal.abandonment_criteria`. No call site in `aca_os/` reads that key to make a decision (§4.2). |
| Who evaluates `mission_impact.may_change_mission_state` / `preserve_active_mission` | Nobody. Computed by `_mission_impact_for` (`conversation_state.py:4366-4381`) and stored in the conversational-goal trace; no consumer found anywhere in `aca_os/` (§4.3 — this is a signal ACA-304 did not enumerate). |

## 3. Writers and Readers of `active_mission`

Verified by exhaustive grep of `active_mission` across `aca_os/` (15 files
match; every match was inspected).

| Component | Relationship | Evidence |
| --- | --- | --- |
| `MissionManager` | **Writer.** Sole `MISSION_CREATE` site; sole component that bumps `progress` on completion of a response turn. | `mission_manager.py:28-69`, `71-82` |
| `ConversationState._advance_mission` | **De facto co-decider** for `auto_claim_guidance` content (not a second CognitiveState writer — see §1.4). | `conversation_state.py:4931-4937`, `5483-5530` |
| `ConversationState._mission_with_revision_clarification` | Same category as above: proposes a `waiting_user` transition when a fact revision is ambiguous, adopted the same way. | `conversation_state.py:4939-4945`, `5430-5457` |
| `ConversationState.to_cognitive_state` / `project_from_cognitive_state` | Pure projection, not a decision site — copies whichever `active_mission` it is given in either direction. | `conversation_state.py:312-320` (from CognitiveState), `553` (to CognitiveState) |
| `runtime_executor.py` | Reader only. | line 328 |
| `memory_engine.py` | Reader only (episodic/semantic memory summaries). | lines 103-145 |
| `context_manager.py` | Reader only (`ContextBundle.mission`). | line 47 |
| `narrative_response_composer.py` | Reader only (response phrasing, repetition-complaint repair scoped to `auto_claim_guidance`). | lines 155-188, 372-387 |
| `conversation_objective.py` | Reader only. Part of the separate, currently-uncommitted Conversational-First/LLM-verbalization output layer; unrelated to mission authority. | lines 255-258, 402-404 |
| `operational_work_mapper.py` | Reader only, explicitly documented as producing a **non-authoritative** operational case view. | lines 1119-1121, 1177-1179 |
| `public_conversation_product_layer.py` | Reader, plus the sole non-organic reset/clear path. | lines 1398, 1440, 1483-1484, 1519-1520, 426-428 |
| Everything else in the 15-file match set | Reader only. | grep-verified |

No component other than `MissionManager` (and, narrowly, `_advance_mission`
under the conditions in §1.3-1.4) ever writes `active_mission`. **The
single-writer invariant on the final `CognitiveState.active_mission` field
holds today.** What does not fully hold is the single-*decision*-authority
intent declared in `conversation_state.py:702-711` and
`authority_dependency_graph.py:263`.

## 4. Existing Signals and Their Consumers

Four independent signals already exist in the codebase that are relevant to
mission lifecycle and are not consumed for that purpose. This list is
ACA-304's three plus one this audit found.

### 4.1 `TOPIC_SHIFT` conversational act — unchanged from ACA-304

Real act category, own priority, own `topic_stack` handling
(`conversation_state.py:3353-3362`), own slot-suppression rule
(`_act_suppresses_slot_resolution`, `conversation_state.py:4189`). Every
branch of `update_topic_stack` was re-read for this audit; none touches
`active_mission`. `mission_manager.py` does not read
`conversation_state.last_conversational_act` anywhere (grep-verified) — it
has no code path to consume this act even if it wanted to.

### 4.2 `abandonment_criteria` — unchanged from ACA-304

Declared per-goal at `conversation_state.py:4220`
(`_abandonment_criteria_for`, defined at line 4321), included in the
goal-trace field whitelist twice (`conversation_state.py:1106, 1404`) and
in `semantic_authority_pilot.py`'s field lists (lines 419, 440). No
consumer evaluates it anywhere in `aca_os/`.

### 4.3 `mission_impact.may_change_mission_state` / `preserve_active_mission` — new to this audit

Computed by `_mission_impact_for` (`conversation_state.py:4366-4381`) for
every conversational strategy selection and stored in the conversational
goal's `mission_impact` field. `may_change_mission_state` is explicitly
`True` for `REPAIR` and `CONTINUE` strategies — i.e. the system already
labels certain turns as ones where the mission *should* be reconsidered —
and nothing reads that label. This is the same write-only pattern as §4.2,
one layer closer to the goal/strategy machinery instead of the raw act.

### 4.4 `MissionLifecycleStatus.COMPLETED` / `SUSPENDED` — new to this audit

`MISSION_LIFECYCLE` (`conversation_state.py:86-122`) legally allows
transitions into `completed` from `ready_to_progress`, `progressing`, and
`waiting_user`→(indirectly), and into `suspended` from every other state.
`_legacy_mission_status` (`conversation_state.py:5575-5580`) reads these
two values to map them to the legacy `status` string. But
`_mission_status_for` (`conversation_state.py:5533-5542`), the only
function in the codebase that computes a *target* lifecycle status, has
exactly four possible outputs — `waiting_user`, `progressing`,
`ready_to_progress`, `gathering_information` — and a default of
`initialized`. `completed` and `suspended` are unreachable in the live
system today. This is a materially built, then abandoned mid-way,
mechanism: someone already designed a mission that can finish or pause,
and no caller was ever written to request either outcome.

### 4.5 A related, narrower, already-shipped repair (not a lifecycle mechanism)

`_is_repetition_complaint` / `_compose_repetition_repair`
(`narrative_response_composer.py:147-171, 449-`) detects when the user
explicitly complains about repetition (e.g. "ya te dije eso") and produces
a softer response — but only for `auto_claim_guidance` missions, and only
at the language-composition layer. It does not change mission state, act
classification, or planning; it is worth noting as evidence that this
general problem area has already been patched locally more than once, in
different layers, without a unifying authority decision — the same
observation ACA-304 made about the three signals it found, now reinforced
by this fourth instance in a completely different subsystem.

## 5. Architectural Alternatives

These are ACA-304's four options (§7 of that document), re-evaluated
against the corrected evidence in §1.3-1.4 and §4.4 above. Ordered
narrowest to broadest, as in ACA-304.

### Option 1 — Wire the already-declared signals into `MissionManager`, change nothing about detection

Make `MissionManager.before_kernel` read `conversation_state.last_
conversational_act` (specifically `TOPIC_SHIFT` and the
`impact.mission_reevaluation` flag) and `abandonment_criteria`, and, when
present, evaluate whether the current mission should be reclassified using
the existing keyword logic. This closes §4.1-4.3's wiring gap without
improving detection quality (§ "cognitive" dimension in ACA-304 §5 remains
unaddressed). Given §1.3, this option should explicitly also decide what
happens to the *already-wired* `auto_claim_guidance` path — today it is
adopted unconditionally by equality check, not evaluated; Option 1 done
properly must bring that path under the same evaluation discipline as the
new signals, not leave it as a second, ungated mechanism.

### Option 2 — Improve topic/relevance detection as its own Semantic Firewall package

Unchanged from ACA-304. Belongs in the FW-6..FW-12 sequencing (ACA-100),
not this decision. Confirmed still out of scope here (§11).

### Option 3 — Add an explicit, gated mission-transition-proposal step

Generalize the pattern already proven twice in this codebase — once in
`_advance_mission`/`_mission_with_revision_clarification` (which already
produce a `{mission_before, mission_after, from_status, to_status, reason,
facts_considered, component}` trace shape, `conversation_state.py:5521-5530,
5448-5457`) and once, independently, in `semantic_authority_pilot.py`'s
`select_conversational_act_authority`/`select_conversational_goal_authority`
(confidence threshold, scoped allowlist, explicit `rollback_reason`,
`conversational_act_authority_selector` now registered as a first-class
runtime component, `runtime.py` diff lines ~186-213) — into a single
mission-transition gate inside `MissionManager.before_kernel`. Any
component (fact/slot advancement, topic-shift detection, abandonment
evaluation) may compute a *proposed* transition; only `MissionManager`
evaluates and accepts or rejects it, atomically, with a logged reason. This
is the option most consistent with what the codebase's own architecture
tooling already declares as intent (§1.5) and with the gated-authority
precedent HANDOFF.md and CLAUDE.md already require for authority
migrations.

### Option 4 — Repetition/frustration circuit breaker

Unchanged from ACA-304, still viable as an independent, small addition;
now additionally evidenced by §4.5's finding that a much narrower version
of this idea has already been built once, locally, at the language layer,
for one mission type only.

## 6. Risks Per Alternative

| Alternative | Primary risk | Mitigation already implied by this repository's own precedent |
| --- | --- | --- |
| Option 1 alone | Leaves the `auto_claim_guidance` path (§1.3) as an ungated exception once other signals are gated — an inconsistency, not a fix. Also leaves "cognitive" detection quality unaddressed (ACA-304 §5), so naturalistic phrasing like "¿Dios existe?" still would not trigger anything. | Fold the existing `auto_claim_guidance` adoption path into the same gate being built for the new signals (§5, Option 1 note); sequence Option 2 separately, as ACA-304 already recommended. |
| Option 2 alone | Large-scope, multi-package effort (ACA-100 territory); does nothing for `MissionManager`'s missing consumption contract even if detection improves. | Do not attempt without Option 1/3 in place first; a perfect detector wired to nothing still fails the ACA-304 conversation. |
| Option 3 | Real risk of recreating a second planner or a second authority if the "proposal" step is allowed to write state directly instead of routing through `MissionManager`'s evaluation. This is exactly the ACA-104/FW-11 failure mode CLAUDE.md and HANDOFF.md warn about, and §1.4 shows the codebase is already halfway into this shape today (`_advance_mission` computing content that `MissionManager` merely echoes). | Enforce, as a hard invariant (§8), that proposals are inert data until `MissionManager` accepts them — mirroring `select_conversational_act_authority`'s shape, where the pilot function returns a decision dict and only the caller (`conversation_manager`) applies it as state. |
| Option 4 | Blunt: breaks the loop without understanding why, and, per §4.5, has already been implemented once in a narrower, uncoordinated form (response-repair layer, `auto_claim_guidance`-only). A second, uncoordinated implementation at the mission layer would be a second local patch, not a fix. | If pursued, implement it as one input signal into the same Option 3 gate, not as an independent mechanism, so `narrative_response_composer.py`'s existing repetition detection and any new mission-level circuit breaker do not diverge. |
| Doing nothing (status quo) | `general_orientation` missions — the majority of real conversations that are not an explicit auto-claim flow — have zero reevaluation mechanism, confirmed unchanged by this audit. `COMPLETED`/`SUSPENDED` remain permanently unreachable, meaning even the one mission type with a real lifecycle machine cannot actually finish or pause. | None; this is the current, verified state. |

## 7. Recommended Decision

**`MissionManager` remains the sole authority that writes
`CognitiveState.active_mission`.** No second writer, no second planner.
This is not an assumption carried in from ACA-019/ACA-301 or from the
declared-but-partially-inaccurate ownership metadata (§1.5) — it is what
§3's exhaustive writer audit confirms is already true for the field itself,
and it is the option that requires the least structural change while
closing the actual gap.

**What changes conceptually:** `MissionManager.before_kernel` gains a
single, explicit evaluation responsibility — *given the current mission and
zero or more proposed transitions from other components, decide whether to
accept, reject, or partially accept each one, and record why.* This
replaces two things that exist today in an unexamined form:

1. The bare equality-check adoption of `ConversationState`'s
   `_advance_mission` output (§1.3-1.4), which today is not evaluated at
   all — it is accepted whenever it exists, for one mission type only.
2. The complete absence of any consumption of `TOPIC_SHIFT`,
   `mission_reevaluation`, `abandonment_criteria`, or
   `may_change_mission_state` (§4.1-4.3).

Both become instances of the same conceptual mechanism: a proposal is
computed by whichever component already computes the relevant evidence
(unchanged — `ConversationState` keeps computing fact/slot advancement and
topic/act signals; `SemanticAuthority`/Legacy keep computing conversational
acts), and only `MissionManager` decides whether that proposal becomes the
new authoritative mission.

This is Option 3 from §5, explicitly sequenced to absorb Option 1's wiring
work as its first concrete instance (start by wiring `abandonment_criteria`
and `TOPIC_SHIFT` for `general_orientation` missions — the exact case that
failed in ACA-304's reproduction — and by bringing the existing
`auto_claim_guidance` path under the same gate rather than leaving it
exempt). Options 2 and 4 remain explicitly out of scope for this decision
(§11).

## 8. Invariants

1. **Single writer.** `CognitiveState.active_mission` has exactly one
   writer: `MissionManager`, via `.evolve(...)`. No other component may
   call `.evolve(...)` with `active_mission` in its payload.
2. **Proposals are inert.** Any mission-relevant computation produced
   outside `MissionManager` (fact/slot advancement, topic-shift detection,
   abandonment evaluation, future semantic signals) is a passive value
   until `MissionManager` evaluates it. It must not be adopted by mere
   presence or mere equality, the way `_advance_mission`'s output is
   adopted today.
3. **Every transition is evidenced and traceable.** Reuse, do not
   reinvent, the trace shape already in production:
   `mission_before`/`mission_after`/`from_status`/`to_status`/`reason`/
   `facts_considered`/`component` (`conversation_state.py:5521-5530`).
   Every accepted or rejected proposal must produce this shape, including a
   `rollback_reason`-equivalent field when rejected, mirroring
   `semantic_authority_pilot.py`'s pattern.
4. **`type` changes are a distinct, explicit transition kind**, not a
   side effect of a progress or status update. A mission being replaced
   (e.g. `general_orientation` -> `auto_claim_guidance` mid-conversation)
   must be observably different from a mission merely advancing within its
   own type.
5. **Declared-but-unreachable states must become reachable or be
   removed.** `completed` and `suspended` (§4.4) may not remain permanent
   dead code once this decision is implemented; ACA-305B must either wire a
   real path to each or explicitly retire them with a documented reason.
6. **No LLM authority.** Mission transition decisions must be grounded in
   facts, slots, or classified signals meeting an explicit confidence/scope
   threshold — never in LLM verbalization output, consistent with
   CLAUDE.md's existing constraint and with the fact that the currently
   uncommitted LLM-verbalization work (§1.3 note; `step_handlers.py`,
   `conversation_objective.py`) is entirely confined to the output/response
   layer and has no mission-authority surface today. This decision must not
   create one.
7. **Gated promotion, not a silent always-on change.** Any new signal
   being wired into mission-transition authority (starting with
   `abandonment_criteria` and `TOPIC_SHIFT`) follows the same
   shadow -> benchmark -> gated atomic selection -> rollback discipline
   already used for `ConversationalAct`/`ConversationalGoal`
   (`semantic_authority_pilot.py`), not a direct unconditional wire-up.
8. **Rollback is mechanical.** Because every transition retains
   `mission_before`, reverting a bad transition is always "restore the
   prior mission snapshot" — this must remain true for every new
   transition kind added under this decision, including `type` replacement.

## 9. Conceptual Transition Contract

Not a class, not a schema — the shape already validated twice in this
codebase, generalized in prose:

- **Proposal** (produced by any component): what changed (evidence), what
  transition kind is being suggested (advance-within-type / complete /
  suspend / replace-type / abandon), a confidence or scope qualifier, and
  the component that produced it. This is structurally what
  `_advance_mission`'s return value and `select_conversational_act_
  authority`'s return value already are, independently, today — the
  contract work for ACA-305B is unifying their shape, not inventing a new
  one.
- **Decision** (produced only by `MissionManager`): accept, reject, or
  accept-with-modification, plus `mission_before`, `mission_after` (equal
  to `mission_before` on reject), the reason, and the evidence considered —
  i.e., exactly the trace dict shape already in `conversation_state.py:
  5521-5530`, extended to cover transition kinds beyond fact/slot
  advancement.
- **Effect**: only a `MissionManager`-produced Decision may ever reach
  `CognitiveState.evolve(..., active_mission=...)`.

## 10. Consequences

**If adopted:**

- Closes the exact gap ACA-304 reproduced: `general_orientation` missions
  gain a real (gated, evidenced) path to reevaluation, using signals
  (`abandonment_criteria`, `TOPIC_SHIFT`) that already exist and cost
  nothing new to compute.
- `completed`/`suspended` become reachable, which is required for any
  future "the user's need was resolved" or "we're waiting on something
  external" behavior — currently impossible regardless of what the
  conversation contains.
- Unifies two currently-separate, differently-shaped decision mechanisms
  (`_advance_mission`'s unconditional adoption and the still-unbuilt
  general signal consumption) under one gate, removing the asymmetry
  identified in §1.4 before it can compound the way the FW-11 duplicate
  writer issue did in a different subsystem.
- Reuses proven infrastructure (`semantic_authority_pilot.py`'s pattern,
  the existing trace-dict shape) rather than inventing new machinery,
  matching this repository's own stated preference for narrow, reversible
  change.

**Costs / open work this decision does not resolve:**

- ACA-304 §6 already estimated the wiring work at complexity **M** and the
  combined, safe version at **L** — this audit's finding that
  `auto_claim_guidance` must also be brought under the same gate (rather
  than being a separate follow-up) adds real, if bounded, scope to that
  estimate; ACA-305B should re-baseline it rather than inherit ACA-304's
  number unchanged.
- Detection quality (ACA-304 Option 2 / the "cognitive" dimension) is
  unresolved by this decision on purpose (§11) — naturalistic off-topic
  phrasing still will not be caught until that separate work lands.
- No benchmark coverage exists yet for any of this. CURRENT_STATE.md's
  open item #3 ("add the reproduced topic-shift conversation to the
  permanent conversational benchmark corpus") was checked against
  `benchmarks/conversations/aca_conversational_first_benchmark_v1.json`
  and the `benchmarks/semantic/` corpus during this audit; none contains
  the exact ACA-304 reproduction. It remains open and is a prerequisite
  for gating any implementation of this decision, not merely a nice-to-have.

## 11. Explicitly Out of Scope

- Implementing any of the above. No code, class, or contract was written.
- Redesigning topic/relevance **detection** quality (ACA-304 Option 2) —
  belongs to the Semantic Firewall roadmap (ACA-100), sequenced
  independently.
- Reopening the `semantic_authority_pilot.py` promotion gate's current
  scope (`LOW_RISK_SEMANTIC_ACTS = {"greeting"}`,
  `semantic_authority_pilot.py:17`). No evidence was found that mission
  lifecycle authority requires widening that specific gate — a mission
  transition gate can consume the *Legacy* (already-produced) `TOPIC_SHIFT`
  act and `abandonment_criteria` directly as evidence, without first
  requiring Semantic Authority promotion of those acts. This should not be
  used as justification to expand SA-3 scope as a side effect.
- Restructuring `ConversationState` fields. `active_mission` stays where it
  is; only the write-authority discipline around it is addressed
  conceptually.
- Moving `_advance_mission`'s physical code location out of
  `conversation_state.py`. Whether the proposal-computation logic should
  physically live inside `MissionManager`, stay in `ConversationState` and
  be called by `MissionManager`, or be exposed as its own module is a
  305B implementation decision, not an authority decision.
- The repetition/frustration circuit breaker (ACA-304 Option 4) and the
  existing narrow repetition-complaint repair (§4.5). Neither is blocked by
  this decision; neither is required by it.
- Promoting Candidate Work / Operational Governance / Operational Audit
  Ledger from Shadow. `operational_work_mapper.py`'s use of
  `active_mission` remains a non-authoritative read (§3), unaffected by
  this decision.
- Any change to the LLM verbalization / Conversational-First output layer
  currently uncommitted in the working tree
  (`step_handlers.py`, `conversation_objective.py`, `llm_verbalization.py`,
  `runtime.py`'s component-registry additions). It was inspected only to
  confirm it has no mission-authority surface (§8, invariant 6) and is
  otherwise unrelated to this decision.

## 12. Recommendation for ACA-305B

1. Design the concrete proposal/decision contract described in §9,
   generalizing the two shapes that already exist
   (`_advance_mission`'s trace dict and
   `select_conversational_act_authority`'s decision dict) rather than
   inventing a third shape.
2. Decide, as a small and separate implementation question, whether
   `_advance_mission`'s computation moves physically or is called from
   `MissionManager` in place — explicitly out of scope for this ADR (§11)
   but blocking for 305B.
3. Sequence the first wired signals as: `abandonment_criteria` evaluation
   and `TOPIC_SHIFT` consumption, scoped first to `general_orientation`
   missions (the exact ACA-304 reproduction case), before extending
   `COMPLETED`/`SUSPENDED` reachability or `type`-replacement to
   `auto_claim_guidance`.
4. Require, as an acceptance gate before promotion out of shadow mode: the
   ACA-304 conversation (`Hola` / `Cómo estás?` / `Mis vacaciones` /
   `Ninguno` / `Dios existe?`) added to a benchmark corpus and passing
   without the repeated-question failure, plus a rollback demonstration
   showing a rejected proposal leaves `active_mission` byte-for-byte
   unchanged.
5. Do not begin Option 2 (detection-quality improvement) in the same
   sprint as this wiring work; keep them independently gated and
   independently benchmarked, per ACA-304 §8 and this document's §11.

`CURRENT_STATE.md` is updated separately to reflect that this decision is
closed and evidenced, per the session's closing protocol.
