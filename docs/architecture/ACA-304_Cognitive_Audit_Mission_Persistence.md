# ACA-304 - Cognitive Audit: Mission Persistence Across Topic Change

Status: Investigation only. No code, contract, or document was modified.
Scope: Answer one question with code-level evidence, not hypothesis.
Runtime impact: none

## 0. The Question

> ¿Por qué ACA sigue razonando como si continuara la misma conversación
> cuando, para un humano, el cambio de contexto es evidente?

## 1. Direct Answer

**Because `MissionManager` has exactly one decision point in the entire
official Runtime, and it only fires once.** `aca_os/mission_manager.py:16-22`:

```python
current = state or CognitiveState()
if current.active_mission:
    ...
    return current          # <- once a mission exists, this is the only path taken, forever
```

The classification logic that decides mission *type* (`general_orientation`
vs. `auto_claim_guidance` vs. `knowledge_lookup`, lines 28-69) only executes
when `current.active_mission` is falsy — which, in practice, is only true on
a conversation's first turn. After that, `MissionManager.before_kernel` never
re-examines whether the mission still matches what the user is saying. There
is no code path anywhere in the official Runtime that changes a mission's
`type`, ends it, or asks "is this still relevant?"

This is not a missing feature nobody thought of. The codebase **already
computes three independent signals** that something has changed — a
conversational-act category called `TOPIC_SHIFT`, an `impact.mission_
reevaluation` flag, and a declared `abandonment_criteria` list containing the
literal string `"new_unrelated_topic_detected"` — and **none of the three is
ever read by `MissionManager`**. The system has the vocabulary for this
problem and has had it for a while; it is simply not wired to the one
component that owns the state that needs to change.

Secondarily, even where topic-shift detection exists, it is a narrow lexical
whitelist (`"cambiemos de tema"`, `"otra cosa"`, `"volvamos a lo anterior"`)
in **two independently-maintained copies** (Legacy and Semantic Authority),
neither of which matches naturalistic phrasing like `"¿Dios existe?"` or
`"Mis vacaciones"`. So even if the wiring existed, this specific
conversation would likely still have failed to trigger it. Both problems are
real; the wiring gap is the more severe of the two, because it means a
*perfect* topic-shift detector would still not save this conversation.

## 2. Turn-by-Turn Reconstruction (Real Execution, Not a Trace Read)

The exact conversation was reproduced against the live official Runtime
(`sdk.factory.build_galicia_runtime()` → `ACAOSRuntime.process()`, the same
path Studio/production use), instrumented with the ACA-303 introspection
completeness work (`RuntimeIntrospectionAPI.snapshot()`,
`conversation_state_runtime` record). Every field below is observed, not
inferred.

### Turn 1 — "Hola"

| Field | Value |
| --- | --- |
| Response | `Hola. Contame qué necesitás y te oriento.` |
| `intent_match` | `intent=greeting confidence=0.25 reason=rule_match` |
| `last_conversational_act` | `act=greeting confidence=0.99` (Semantic, promoted — SA-3 gate) |
| `active_mission` (**created here**) | `type=general_orientation status=in_progress next_act=ask_user_need missing=[user_need]` |
| `topic_stack` | 1 entry: `mission:general_orientation` (status=active) |
| `conversation_goal` | `act=greeting intention=respond_to_greeting` |
| `conversation_plan` | `replanning_reason=plan_initialized current_step=understand_user_need` |
| Components that acted | `ConversationManager` (act/goal recognition + Semantic pilot), `MissionManager` (**mission creation, the only creation event in this conversation**), `IntentMatcher`, `ActionPlanner`, `FlowRouter`, `Kernel`, `NarrativeResponseComposer` |

This turn is correct. A mission is created because none existed
(`mission_manager.py:16`, condition false → falls through to classification
at line 46-69). `"hola"` contains none of the `auto_claim_guidance` keywords
(`me chocaron`, `choque`, `accidente`, `siniestro`, `denuncia`) and the
planned flow is not `knowledge_lookup`, so the `else` branch at line 58-68
creates `general_orientation` — the system's generic default, not a
domain-specific inference.

### Turn 2 — "¿Cómo estás?" (the derailment begins here)

| Field | Value |
| --- | --- |
| Response | `Que punto queres resolver primero: el arreglo, la denuncia, la documentacion o los tiempos?` |
| `intent_match` | `intent=fallback confidence=0.0 reason=no_rule_matched` (zero-cost `IntentMatcher` has no rule for this phrase) |
| `last_conversational_act` | `act=pending_answer confidence=0.82 reason=message_answers_pending_question` (**Legacy**, selected) |
| Semantic candidate (discarded) | `act=question confidence≈0.88` (`semantic_authority.py:1077-1078`, the question-mark fallback rule) — **closer to correct, but discarded** |
| Why Semantic lost | `semantic_authority_pilot: authority_selected=legacy authority_reason=confidence_below_threshold` — SA-3's promotion gate only ever promotes `greeting`-type acts (ACA-104/ACA-301 finding, reconfirmed here); any other semantic act, however reasonable, rolls back to Legacy |
| `active_mission` | unchanged: `general_orientation`, `next_act=ask_user_need` (`MissionManager` returned `current` unmodified at line 22 — no classification logic ran) |
| `topic_stack` | still 1 entry, same topic, unchanged |
| `conversation_goal` | `act=pending_answer intention=respond_to_pending_answer` (goal inherits the wrong act) |
| `conversation_plan` | `replanning_reason=plan_still_valid` — **the plan explicitly considered itself still valid** |
| Response text change | Same `next_act` (`ask_user_need`), but a *different, more specific* question text — see §4.3, a separate mechanism (question reformulation) reacting to "same slot asked twice," not to mission or topic |
| Components that acted | `ConversationState.recognize_conversational_act` (Legacy, wins), `SemanticAuthority.interpret` (computes a better answer, discarded), `semantic_authority_pilot.select_conversational_act_authority` (the gate that discards it), `ConversationState.plan_conversation` (`plan_still_valid`), `MissionManager` (no-op) |

This is the turn where the failure is committed. `_looks_like_pending_answer`
(`conversation_state.py:5856-5867`) requires only that a pending slot exists
and either an explicit or "contextual" match is found — it does not require
the answer to be *about* the pending question's subject. Once
`PENDING_ANSWER` wins (priority 95, `conversation_state.py:4154`, second
only to `CORRECTION`), everything downstream treats the turn as "the user is
answering `user_need`," including the plan, which sees no reason to replan.

### Turn 3 — "Mis vacaciones"

Identical shape to turn 2: `intent=fallback`, `act=pending_answer`
(confidence 0.82, same reason), `conversation_plan.replanning_reason=
plan_still_valid`, identical response. Semantic candidate this time is
`new_information` (the final fallback in `semantic_authority.py:1079`, since
there is no question mark and no marker match) — still discarded, still
irrelevant to the outcome since Legacy's `pending_answer` wins regardless of
what Semantic proposes for any non-`greeting` act.

### Turn 4 — "Ninguno" (an explicit, unambiguous opt-out)

Same classification: `act=pending_answer`. `_is_minimal_affirmation_or_
negation("ninguno")` is `False` — `"ninguno"` is not in the recognized
negation set (`{"no", "nop", "para nada", "negativo"}`,
`conversation_state.py:5887-5894`), so it doesn't even get the higher
`0.9` confidence that a literal `"no"` would; it scores through the
"contextual" branch of `_looks_like_pending_answer` at `0.82` like the
others. There is no mechanism anywhere that interprets "ninguno" as *declining
the mission itself* rather than *answering with a slot value of "none."*
Same mission, same plan, same response.

### Turn 5 — "¿Dios existe?"

Same classification: `act=pending_answer` (0.82). Semantic candidate is
`question` again (question mark present). Same mission, same response,
verbatim identical to turns 2-4.

### Summary table

| Turn | Message | Legacy act (won) | Semantic act (discarded) | `intent_match` | Mission changed? | Plan replanned? | Response |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Hola | greeting (semantic, promoted) | greeting | greeting | created | initialized | greeting |
| 2 | ¿Cómo estás? | pending_answer | question | fallback | no | no (`plan_still_valid`) | reformulated user_need question |
| 3 | Mis vacaciones | pending_answer | new_information | fallback | no | no | identical |
| 4 | Ninguno | pending_answer | new_information | fallback | no | no | identical |
| 5 | ¿Dios existe? | pending_answer | question | fallback | no | no | identical |

## 3. Authority Map

| Question | Answer, with evidence |
| --- | --- |
| **Dónde nace la misión** | `MissionManager.before_kernel`, `mission_manager.py:28-69`, exactly once per conversation — only when `current.active_mission` is falsy. Classification is keyword matching on the raw first message plus the `zero_cost` planned flow; it is never re-run. |
| **Quién tiene autoridad para cambiarla** | Nobody, after creation. `after_kernel` (`mission_manager.py:71-82`) only ever *increases* `progress`. `_advance_mission` (`conversation_state.py:5483-5490`) can update `missing`/`blockers`/`slots` *within* a mission, but is hardcoded to `if active_mission.get("type") != "auto_claim_guidance": return None` — it does not run for `general_orientation` at all, and even when it runs for `auto_claim_guidance`, it never touches `type`. |
| **Quién tiene autoridad para finalizarla** | Nobody, organically. The only mission-clearing path found is `PublicConversationProductLayer.reset()` (`public_conversation_product_layer.py:426`, invoked only via an explicit `public_action_id == "reset_conversation"` UI action, `run_public_conversation_product_layer:1673-1674`) — a manual "start over" button, not conversational understanding, and it lives in the public adapter layer, not the canonical `ConversationState`/`MissionManager` path. |
| **Quién decide que la conversación cambió de tema** | `_mentions_topic_shift` (Legacy, `conversation_state.py:5925-5943`) and a separate, differently-worded lexical list inside `SemanticAuthority._conversational_act` (`semantic_authority.py:1069`). Both are keyword whitelists requiring the user to say something like "cambiemos de tema" almost verbatim. Neither fired for any turn in this conversation. |
| **Quién decide abandonar una misión** | Nobody. `_abandonment_criteria_for` (`conversation_state.py:4321-4326`) *declares* criteria such as `"new_unrelated_topic_detected"` and stores them as metadata inside the conversational goal object (`conversation_state.py:4220`), but grep across `aca_os/` finds zero call sites that ever *evaluate* whether a declared criterion has been met. It is write-only metadata. |
| **¿Existe un mecanismo explícito de "topic shift"?** | Yes, a real one: `ConversationalActType.TOPIC_SHIFT` is a first-class act category with its own priority (86, `conversation_state.py:4157`), its own `update_topic_stack` handling that suspends the old topic and pushes a new one (`conversation_state.py:3353-3361`), and it even suppresses slot resolution when selected (`_act_suppresses_slot_resolution`, line 4189). **It only ever manipulates `topic_stack`. It never touches `active_mission`, in any branch, for any direction.** Confirmed by reading every branch of `update_topic_stack`. |
| **¿Existe un mecanismo de "conversation reset"?** | Yes, but only as an explicit, user-initiated UI action in the public/legacy adapter layer (`public_conversation_product_layer.py`), unconnected to organic conversation understanding, and outside the canonical `ConversationManager`/`MissionManager` path this conversation went through. |
| **¿De dónde viene el problema?** | Not from one component with a bug. From an **integration gap between three components that were each built correctly for their own narrow job**: `ConversationState` computes a rich `TOPIC_SHIFT` act (when its lexical trigger fires) and declares abandonment criteria it never checks; `MissionManager` was built to create a mission once and had no requirement to ever reconsider it; nothing in `ACAOSRuntime.process()` ever calls `MissionManager` again after the first turn, and nothing passes it the conversational act, topic transition, or abandonment evaluation even if it wanted to consume them (`mission_manager.before_kernel`'s signature takes `event`, `state`, `conversation_state` — `conversation_state.last_conversational_act` *is* available to it, it is simply never read). |

## 4. Where Exactly the Context-Change Signal Is Lost

There isn't one point of loss — there are three redundant signals, and all
three are severed from `MissionManager` at a different point each:

### 4.1 The detection layer (would need to fire, and mostly doesn't)

- `_mentions_topic_shift` / `SemanticAuthority`'s topic-shift markers: lexical
  whitelists, didn't match any of "¿Cómo estás?", "Mis vacaciones",
  "Ninguno", "¿Dios existe?". **This is a real, separate defect** — even a
  perfectly-wired mission-reevaluation mechanism would not have been
  triggered by content-based detection here, because there is no
  content-based detection; there is only phrase-matching.
- The one signal that *did* fire correctly at the semantic layer — `question`
  for turn 2, distinct from Legacy's `pending_answer` — was computed and then
  discarded by the SA-3 promotion gate, which only ever promotes `greeting`
  (ACA-104/ACA-301, reconfirmed with live evidence here). This is not a new
  defect; it is the known, deliberate scope of the current Semantic Authority
  pilot, encountered here in a place where its narrowness has a real
  behavioral cost.

### 4.2 The signal-to-authority wiring (severed even when detection works)

Even in the hypothetical case where `_mentions_topic_shift` *had* matched:

- `update_topic_stack` would push a new topic and suspend the old one — but
  never call, notify, or otherwise inform `MissionManager`.
- `impact.mission_reevaluation: True` is set on the `PENDING_ANSWER` and
  `CORRECTION` act candidates (`conversation_state.py:3941, 3961`) — a field
  that already encodes "this should cause the mission to be reconsidered" —
  and is never read by anything. It is discarded the moment the candidate
  dict is set as `last_conversational_act`; no consumer greps for
  `impact.mission_reevaluation` anywhere in `aca_os/`.
- `abandonment_criteria` on the conversational goal similarly declares intent
  ("if `new_unrelated_topic_detected`, this goal should be abandoned") that
  is never evaluated.

### 4.3 A compounding, secondary effect (not the cause, but makes it worse)

`_reformulated_question_for_slot` (`conversation_state.py:2344-2364`) fires
when the same slot is asked twice in a row
(`_should_reformulate_selected_question`, lines 2324-2341) and rewrites the
question to a more specific, "helpful" version. For `user_need`, that
rewrite is a hardcoded, insurance-claim-specific multiple choice: *"el
arreglo, la denuncia, la documentación o los tiempos"*. Because the system
believes (wrongly, per §4.1-4.2) that it is still waiting on the exact same
question, it "helpfully" narrows an already-wrong question into a more
specific and more obviously irrelevant one after the very first
misclassified turn — which is why turn 2's response already looks like a
non-sequitur about car insurance in reply to "¿Cómo estás?", not merely a
repeated open question. This mechanism is not itself the root cause; it is a
downstream amplifier that makes the root cause more visible and more jarring
to a human reader.

### 4.4 One existing precedent worth noting

The deprecated public/legacy stack (`PublicConversationState`, feeding
`ConversationState.from_public_state`, `conversation_state.py:6704-6712`)
already tracks `fallback_count`, `confusion_count`, and `frustration_count`
— a rudimentary repetition/frustration signal that never made it into the
canonical `ConversationState`/`MissionManager` path this conversation
actually used. It is dead for the official Runtime today, but it is
evidence that a "the user seems stuck, something is wrong" concept was
already considered valuable once, in a different part of the system.

## 5. Classification

This is **not primarily a bug in one component**. Classified across the
requested dimensions:

| Dimension | Applies? | Why |
| --- | --- | --- |
| **Arquitectónico** | **Yes — primary.** `MissionManager` has no re-invocation contract beyond turn one; nothing in `ACAOSRuntime.process()` treats mission selection as a per-turn decision the way `IntentMatch`/`ActionPlan` already are. This is a structural gap, not a wrong condition inside an existing function. |
| **De autoridad** | **Yes — primary, and inseparable from the architectural gap.** Three components each compute a legitimate signal (`TOPIC_SHIFT` act, `mission_reevaluation` impact flag, `abandonment_criteria`) and none has been granted, or grants itself, authority over `active_mission`. Authority for ending/changing a mission simply does not exist anywhere in the official Runtime. |
| **Cognitivo** | **Yes — contributing.** Topic-shift and off-topic detection are lexical whitelists, not semantic understanding of relevance. This is a real gap independent of the wiring gap: naturalistic phrasing that a human would immediately read as "this has nothing to do with your question" produces no distinguishing signal anywhere in the pipeline (Legacy or Semantic). |
| **De estado** | **Partially.** `ConversationState`/CSM ownership itself is not at fault — the state model has the *fields* to represent a changed topic (`topic_stack`) and a stale mission (`active_mission`), and correctly keeps them factually accurate as far as each component's own narrow job goes. The defect is in what reads and cross-references that state, not in the state model's shape. |
| **De planificación** | **Contributing, not causal.** `ConversationPlan`'s `plan_still_valid` determination is *correct given its inputs* — nothing told it the mission changed, so "still valid" is the right conclusion from wrong premises. The reformulation mechanism (§4.3) is a planning-layer amplifier of the underlying failure, not its source. |

**In one sentence:** this is an authority gap wearing a cognitive-detection
costume — even a flawless topic-shift detector would not fix this
conversation unless it were also wired into `MissionManager`, and the wiring
does not exist for any signal today, correct or not.

## 6. Complexity Estimate

Relative to this repository's own recent work (ACA-104's FW-11 collapse as
`S`, ACA-303's registry completion as `S`-`M`):

| Piece | Complexity | Why |
| --- | --- | --- |
| Making `_mentions_topic_shift` (or its semantic equivalent) detect naturalistic off-topic messages, not just explicit meta-commands | **M-L** | This is close to the exact shape of problem the Semantic Firewall packages (FW-6 through FW-12) already exist to solve carefully, one artifact at a time, with adversarial-benchmark-gated promotion (ACA-100, ACA-200). It is not a small lexical-list edit; doing it safely means reusing that existing, deliberate methodology, not inventing a new one. |
| Wiring *any* existing signal (`TOPIC_SHIFT` act, `mission_reevaluation` impact, `abandonment_criteria`) into `MissionManager` so it can actually change or end a mission | **M** | The signals already exist; this is primarily a new consumption point in `MissionManager.before_kernel`, plus deciding what "changing a mission mid-conversation" is allowed to do to already-collected facts/slots — not a new detection problem, but a real behavior change to a component ACA-200 classified `TRANSITIONAL` and flagged for exactly this kind of future work ("MissionManager correctly owns missions, but still selects claim/general missions by lexical matching"). |
| Doing both together, safely, without becoming a second BPM-style planner or a second decision authority | **L** | This is squarely the risk ACA-019/ACA-301 already warned about for *any* work in this area: introducing mission-reevaluation authority incorrectly could create exactly the kind of duplicate/competing-authority bug ACA-104 just spent two sessions fixing, one layer up. Any implementation must follow the same shadow-first, atomic-selection, benchmark-gated discipline already proven for Semantic Authority — not because it is required by policy, but because this repository has direct, recent, first-hand evidence of what happens when that discipline is skipped. |

None of this is small. All of it is achievable by extending existing
components and existing promotion discipline — it does not require a new
runtime, planner, or state model.

## 7. Possible Solution Strategies (Not Implemented, Not Recommended Yet)

Presented as options, not a plan. Ordered roughly from narrowest to
broadest scope.

1. **Wire the already-declared signals, change nothing about detection.**
   Make `MissionManager.before_kernel` read `conversation_state.last_
   conversational_act` and, specifically, the existing
   `impact.mission_reevaluation` flag and `TOPIC_SHIFT` act; when present,
   allow (not force) reclassification using the *same* keyword logic already
   used for mission creation. This fixes the wiring gap (§4.2) without
   touching detection quality (§4.1) at all. Cheapest option; leaves the
   "¿Dios existe?" case unfixed, since the lexical trigger still wouldn't
   fire — but it would fix the case where a user *does* say "cambiemos de
   tema" today, which currently does nothing to the mission either.

2. **Improve off-topic/relevance detection as its own Semantic Firewall
   package**, following the existing FW-6..FW-12 methodology (shadow mode,
   adversarial benchmark, atomic promotion) rather than editing the lexical
   whitelist directly. This treats "is this message relevant to the current
   mission" as a semantic classification problem worth the same rigor as
   `ConversationalAct`/`ConversationalGoal` already received, and would
   naturally produce the *causal* signal `MissionManager` would need — but it
   is a multi-package-scale effort, not a quick fix.

3. **Add an explicit "mission relevance" evaluation step**, analogous to
   `_advance_mission` but inverted: after N turns where the message does not
   advance any mission slot and is not recognized as relevant, surface a
   *candidate* mission change (not an automatic one) for `MissionManager` to
   accept, mirroring the atomic-selection-with-rollback pattern already used
   for Semantic Authority — i.e., treat "should the mission change" itself
   as a gated authority decision, not an unconditional side effect.

4. **Do nothing to detection or wiring; add a repetition/frustration circuit
   breaker instead**, reviving the dead `fallback_count`/`confusion_count`
   concept already present in the deprecated public stack (§4.4) into the
   canonical path: after N consecutive turns with `intent=fallback` and no
   plan progress, break out of the current mission's question loop
   regardless of *why* — a blunter, cheaper, less semantically satisfying
   fix that would have caught this exact conversation by turn 3 or 4 without
   requiring the system to understand *what* changed, only *that* nothing
   is working.

These are not mutually exclusive; (1) and (4) are cheap, defensive, and
plausible even as a same-sprint pair. (2) is a proper long-term fix but
belongs in the Semantic Firewall roadmap's own sequencing (ACA-100), not a
standalone effort. (3) is the architecturally cleanest match to how this
repository already solves exactly this class of problem elsewhere.

No option is proposed here as a recommendation for what to build. That is a
separate decision this document does not make.

## 8. Recommendation for Next Technical Sprint

**Do not implement a fix yet.** This audit found a real, well-evidenced
defect, but implementing option 1, 3, or 4 above without first deciding
which shape of authority `MissionManager` should have is exactly the kind of
premature-implementation risk ACA-019/ACA-301 already flagged for this
general area (mission/work authority), and this document's own complexity
estimate (§6) explicitly warns against introducing mission-reevaluation
authority without the same discipline that made Semantic Authority's rollout
safe.

The recommended next sprint is therefore an **architecture decision**, not
code: a short ADR choosing between strategies 1/3/4 in §7 (or an explicit
combination and sequencing of them), written with the same rigor as
ACA-019/ACA-301 — because this is structurally the same kind of question
("should X component gain reevaluation/abandonment authority over Y state,
and if so, through what gated mechanism") that those two documents already
answered once for the Operational Work Model. That precedent should inform
the decision, not be re-derived from scratch.

Separately, and independently of that decision: this conversation is
exactly the kind of real, messy, multi-turn evidence ACA-200's
`START_REAL_WORLD_TESTING` recommendation was asking for. It should be
added to the permanent conversational benchmark corpus (as a regression
fixture, not yet as a target for a specific fix) so that whichever solution
is eventually chosen has an automated check to prove it actually resolves
this exact case before being considered done.
