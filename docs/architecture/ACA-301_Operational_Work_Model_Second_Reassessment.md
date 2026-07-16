# ACA-301 - Operational Work Model: Second Reassessment

Status: Architecture review only
Scope: Critical re-evaluation of the "Operational Work Model" hypothesis against the current repository, informed by ACA-006, ACA-019, ACA-024, and everything built since (ACA-1xx Semantic Firewall, ACA-2xx LLM runtime, ACA-300 Conversational-First, ACA-104 FW-11 resolution)
Runtime impact: none
Code impact: none

## 0. Question Under Review

The hypothesis under review, stated by the requester:

> ACA no debería modelar principalmente una conversación, sino el trabajo que
> realiza un rol de servicio. La conversación sería únicamente la interfaz
> visible de ese trabajo.

This is not a new question in this repository. It was already investigated
twice, in depth, with code-level evidence:

- **ACA-006** (Sprint 73) froze an architectural analysis of exactly this
  hypothesis and produced a reuse map, a gap list, and a six-sprint roadmap.
- **ACA-019** re-evaluated ACA-006 against the repository as it stood after
  Sprints 74-79 (Candidate Work, Case State Projection, Governance Gate,
  Audit Ledger, first tool integration) and concluded the hypothesis was
  "directionally correct, but its original shape is too broad."

This document does not repeat that investigation from scratch. It verifies
whether ACA-019's conclusion still holds today, against current code, and
answers the requester's specific questions with that evidence. Re-deriving
the same analysis without checking the prior work first would itself be a
process failure the project has flagged before (ACA-024 exists specifically
because ACA-017/018 overclaimed a status that a later audit had to correct).

## 1. Executive Decision

**The hypothesis is partially correct. It does not justify a new
architectural layer. It justifies reorganizing and, in one place, extending
existing components — the same conclusion ACA-019 reached, which remains
unexecuted and still valid today.**

This corresponds to option 2 of the three offered:

> La hipótesis es parcialmente correcta y alcanza con reorganizar
> componentes existentes.

Nothing built since ACA-019 (Semantic Authority, the Semantic Firewall
masterplan, LLM verbalization, Conversational-First, or the FW-11 duplicate-
writer collapse) closes the gap ACA-019 identified, and nothing in that work
weakens ACA-019's argument. The gap is orthogonal to all of it: those efforts
improved *understanding fidelity* (raw text → structured meaning) and
*response generation* (decision → natural language). None of them touch
*action selection* (understanding → what ACA does). ACA-019's finding that
`ActionPlanner` is a flat `intent → fixed action rule` lookup, with no
notion of role, capability, precondition, or expected outcome, is still true
verbatim in the current source (`zero_cost/action_planner.py`).

## 2. Verification: Has Anything Changed Since ACA-019?

Checked directly against current code, not against documentation claims:

| ACA-019 finding | Still true today? | Evidence |
| --- | --- | --- |
| `ActionPlanner.plan()` is `intent_match → fixed rule`, no capability/case input | Yes, unchanged | `zero_cost/action_planner.py`: signature and rule-table lookup are identical in shape to what ACA-019 describes |
| `map_operational_work()` is called only by `evaluation.py`, never by `ACAOSRuntime.process()` | Yes, unchanged | `grep` for `map_operational_work(` matches only `aca_os/evaluation.py` (5 call sites); zero matches in `aca_os/runtime.py` |
| Duplicate plugin manifest models (`aca_os/plugin_manifest.py` vs `aca_core/platform_plugins.py`) | Yes, unchanged | Both files still exist; `aca_os/plugin_manifest.py` is 308 lines and is still imported by `operational_work_mapper.py`, `operational_governance_gate.py`, `plugin_loader.py`, `plugin_validator.py`; `aca_core/platform_plugins.py` remains the separate, larger (~970-line) system that `plugins/galicia.insurance` actually uses in production |
| `operational_work_mapper.py` is domain-agnostic-in-name, business-specific-in-content | Yes, unchanged | Confirmed by ACA-024 (later, independent audit): `"operational_work_mapper.py" ... "Shadow-only complexity; freeze until authority decision"` |
| Candidate Work / Governance / Ledger are "SHADOW" status | Yes, unchanged | ACA-024: `"Candidate Work, Case State Projection, Operational Governance, Operational Audit Ledger integration ... remain experimental with respect to the official Runtime."` |
| ACA-019's proposed next step ("Operational Work Causality Validation" Sprint) | Never executed | No later `docs/architecture` document addresses it; the numbered series moves directly from ACA-024 (forensic audit) to ACA-027 (Semantic Authority) — the project pivoted to a different problem instead |

Conclusion of this section: **the repository is still exactly at "Phase 0 —
Freeze and Baseline"** of ACA-019's own six-phase migration plan. Between
ACA-019 and today, the project invested in a different, legitimate axis of
improvement (semantic interpretation fidelity, then response generation),
and the operational-work question was set aside, not resolved and not
disproven. Re-opening it now is reasonable; re-deriving it from zero would
not be.

## 3. Answering the Specific Questions

### 3.1 Does a real conceptual gap exist between conversational understanding and action selection?

Yes, and it is narrower than the original hypothesis implies. It is not a
gap in *information* — nearly everything an operational decision would need
(facts, mission, slots, evidence, plugin capability declarations, tool and
policy availability) already exists as read-only projections. It is a gap in
*causal ordering and authority*: today, `ActionPlan` is chosen from
`intent_match` alone, before `ConversationIntentModel`, `InformationGainPlan`,
`ConversationPlan` and `ConversationResponsePlan` are even built (confirmed
again by the FW-11 investigation: the post-Mission planning block runs
*after* `ActionPlanner`/`FlowRouter`/`ExecutionPlan` are already fixed). The
runtime currently cannot answer, before it starts planning a response:

```text
What useful operation am I selecting now, from this role, for this case?
```

### 3.2 Is that gap already covered by existing components?

Mostly by data, not by decision. `operational_work_mapper.py` produces a
rich candidate-work projection with strong benchmark numbers (Candidate Work
Recall 100%, Ranking Accuracy 98.91-100%, per ACA-019 §5.1), but it is
structurally disqualified from being the answer as it stands, for a specific
and verifiable reason: it is a *post-hoc* mapper. It reads the current
turn's `ConversationResponsePlan`, `ConversationFulfillment` and execution
outcomes — artifacts that only exist *after* a decision was already made and
a response already composed. A component that reads this turn's own output
cannot validly be the upstream authority for this turn's decision; that
would be circular. This is ACA-019's causality rule (§16), and it is the
single most important finding in the prior investigation — more important
than the benchmark numbers, which measure the wrong thing (parity with a
decision already made, not correctness of an upstream decision that doesn't
exist yet).

### 3.3 Would an Operational Work Model be a new concept, or a rename?

Neither, cleanly. It splits in two:

- **~90% is relocation, not invention.** Candidate detection, ranking,
  blocker/preparation/completion classification, and outcome vocabulary
  already exist in `operational_work_mapper.py`. The work is moving this
  logic to read *pre-decision* state only, and moving its output from an
  evaluation-only artifact to a real input consumed by `ActionPlanner`.
- **One genuinely new thing.** `ActionPlanner` itself would have to change
  shape, from a fixed lookup table to a component that ranks candidate
  actions against role capabilities and case state. That is a real change to
  where selection authority lives, even though it does not require a new
  component, layer, or runtime.

Calling this a "rename" would understate the causality-ordering change
required. Calling it a "new architectural layer" would overstate it — it is
an evolution of one existing authority (`ActionPlanner`), not the addition
of a second one.

### 3.4 Exact responsibilities

Four, matching ACA-019 §11, re-verified as still the correct and minimal set:

1. Enumerate available operational capabilities for the active role, sourced
   from a single canonical plugin/domain capability catalog (which does not
   currently exist — see §5).
2. Rank candidate work from CSM evidence available *before* this turn's
   response planning begins.
3. Bind the selected candidate to an executable flow (`FlowRouter`) and
   record it in `ExecutionPlan` — it does not execute anything itself.
4. Project the actual work outcome, after execution, back into response
   planning and the audit trail — as a derived fact, not a new persistent
   state.

It must explicitly **not**: execute tools, generate response text, replan
dialogue continuity, decide authorization, or persist a second case-state
store. All of those remain owned by `RuntimeExecutor`/`ToolEngine`,
`NarrativeResponseComposer`, `ConversationPlan`, `PolicyManager`, and
`ConversationState`/CSM, respectively — unchanged.

### 3.5 Where would it live in the Runtime?

Between `IntentMatch` and the decision currently made by `ActionPlanner`,
inside `ACAOSRuntime.process()` — specifically, feeding `ActionPlanner`
rather than replacing or bypassing it. Concretely, this is the same
architectural slot the Semantic Authority pilot occupies for
`ConversationalAct`: a projection computed early, offered to an existing
authority, which may accept or reject it under an explicit, atomic,
rollback-capable selection rule. This repository already has a proven
pattern for exactly this kind of introduction (see §6).

It must **not** live downstream of `ConversationPlan` or
`ConversationResponsePlan` (too late — those already assume a selected
action exists) and must not live inside `NarrativeResponseComposer` or
`PolicyManager` (both are explicitly barred from selecting work, per
ACA-019 §9, for good reason: language generation must not invent operations,
and governance must not silently pick a different one than what it is
reviewing).

### 3.6 What would it consume?

- `ConversationState` (facts, active mission, focus, topic, slots, evidence,
  user signals) — read-only, no new field ownership.
- `IntentMatch` (existing).
- A **consolidated** plugin/domain capability catalog — this does not exist
  yet in usable form (§5) and is a prerequisite, not a parallel task.
- Current tool and policy availability signals (`ToolExecutionContract`
  metadata, existing `PolicyResult` shape) — availability only, not a
  decision.
- Prior persisted receipts/evidence (e.g. a completed `handoff_package`),
  where relevant to avoid repeating already-completed work.

It must explicitly **not** consume this turn's `ConversationResponsePlan`,
`ConversationFulfillment`, `ExecutionStepOutcome`, or response text — the
exact set of things the current `operational_work_mapper.py` reads today,
and the exact reason it cannot be promoted unchanged.

### 3.7 What would it produce?

One derived, turn-scoped decision record — not a new persistent state,
stored in `derived_state` exactly like every other turn-scoped projection
already is (`ConversationIntentModel`, `SemanticProjection`, and, as of
ACA-104, the single surviving write of `ConversationPlan` itself): ranked
candidates, the selected immediate work item, evidence, confidence,
selection reason, expected outcome, and blockers. Consumed by:

- `ActionPlanner`, to make the selection.
- `InformationGainPlan`, so that question value is scored against "does this
  answer change or unlock the selected operation," not just conversational
  completeness.
- `ConversationResponsePlan` / `NarrativeResponseComposer`, after execution,
  to communicate the *actual* outcome rather than an inferred one.

### 3.8 What current contracts could simplify or disappear?

- **`operational_work_mapper.py`'s post-hoc read mode** should disappear
  once a pre-decision mode reaches parity — it is not a simplification
  target, it is a correctness defect (wrong causal direction) that happens
  to also be complex (1,745 lines, per ACA-024).
- **The duplicate plugin manifest models** (`aca_os/plugin_manifest.py` vs
  `aca_core/platform_plugins.py`) must consolidate into one canonical schema
  *before* this work starts, not after. Building operational capability
  metadata on top of two unmerged manifest systems would reproduce, at a
  second layer, the exact `domains/galicia` vs `plugins/galicia.insurance`
  duplication already on record from the original repository audit.
- **`operational_governance_gate.py`'s independent allow/block authority**
  should collapse into a pure assessment consumed by `PolicyManager`, which
  remains the single authorization authority — mirroring the "atomic
  selection, no mixed authority" rule already enforced for Semantic
  Authority (ACA-100 series) rather than inventing a new pattern.
- **`ActionPlanner`'s current fixed rule table** does not disappear; it
  becomes the compatibility fallback for capabilities that have not declared
  operational metadata yet (ACA-019 §14.2). This is a deliberate
  non-simplification: removing it early would break every plugin that
  hasn't opted in.
- **Hardcoded domain operation names** in `operational_work_mapper.py` and
  `operational_governance_gate.py` must move to plugin metadata. This is the
  same category of defect independently found in the Kernel itself during
  the original repository audit (`kernel/aca_kernel/operations/basic.py`
  hardcoding insurance-domain response text) — a recurring pattern in this
  codebase of business logic leaking into layers declared domain-agnostic.

### 3.9 Risks of introducing this layer

1. **Duplicate/competing selection authority.** `ActionPlanner`, Candidate
   Work, and any future planner disagreeing is not a hypothetical risk in
   this codebase — it is the exact class of bug just spent two work sessions
   diagnosing and fixing (ACA-104, FW-11): two independent computations of
   the same artifact, one silently winning, with the losing one's output
   unused by anything, undetected until instrumented and measured directly.
   The mitigation is the same one already proven here: exactly one
   authoritative writer, ever, with rollback but never merge.
2. **Promoting the wrong-causality mapper unchanged.** If the existing
   post-hoc `operational_work_mapper.py` were wired into the live path as-is
   (reading this turn's own response/outcome), it would not create new
   business value — it would create a component that reads its own
   conclusion and calls it evidence. This is a subtler variant of the same
   duplicate-authority risk, and the most likely failure mode given the
   mapper already exists and looks "done."
3. **Starting on an unconsolidated capability catalog.** Building
   operational capability metadata across two live, unmerged plugin manifest
   systems guarantees a second version of the domain-pack/plugin split
   already present in this repository. This is a blocking prerequisite, not
   a parallel workstream.
4. **BPM drift.** Capability metadata (preconditions, permissions, expected
   transitions) can calcify into a fixed workflow engine, contradicting the
   "conversation is adaptive" invariant this project has repeatedly defended
   (ADR-0001; the CSM's turn-by-turn evolution model in RFC-0001). Mitigation
   is architectural discipline, not a technical control: only the immediate
   next action is ever committed; capabilities declare what is *possible*,
   never a mandatory sequence.
5. **Optimistic verbalization.** Claiming work was done before a receipt or
   execution outcome exists would directly contradict the product principle
   already enforced elsewhere in this codebase — `plugins/galicia.insurance`
   explicitly blocks claim-status lookups and disables actions it cannot
   really perform (`disabled_reason: "No hay herramienta real conectada..."`).
   An Operational Work Model that lets narrative claim unverified completion
   would undo work already done to keep the system honest about its
   capabilities.
6. **Opportunity cost against the project's own most recent priority.**
   ACA-200 (dated the same day as this session's earlier audit,
   the most recent self-assessment in the repository) concluded
   `START_REAL_WORLD_TESTING`, explicitly *not* new capability layers, and
   explicitly flagged that further shadow-mode infrastructure without live
   validation had already produced false confidence once (the ACA-017/018
   overclaim that ACA-024 had to correct). Opening a new operational-
   authority workstream now competes directly with that recommendation, and
   repeats a pattern visible across the sprint history: building another
   layer of shadow evaluation instead of validating what already exists
   against real, messy conversations.

## 4. Compatibility With Foundational Decisions

| Foundational decision | Compatible? | Why |
| --- | --- | --- |
| ADR-0001 — Remove Planner ("a Planner as a separate component created ambiguity and duplicated responsibility") | Compatible, conditionally | Only if implemented as an evidence projection consumed by the existing `ActionPlanner`, never as a second, independent decision-making component. This is exactly why ACA-019 rejected the original "Operational Work Resolver as new component" framing from ACA-006 and this document reaffirms that rejection. Implemented any other way, it would violate ADR-0001 directly. |
| ADR-0002 — Kernel/OS separation | Compatible | The decision record lives in `ACA OS` (`derived_state`, same as every other turn projection), never in the Kernel. No kernel change is implied. |
| ADR-0003 — Tools produce evidence, never final responses | Compatible | Operational work selection is upstream of tool execution and does not change this; `ToolEngine`/`ToolExecutionContract` are explicitly reused unchanged. |
| ADR-0004 — Conversation Manager belongs to OS, is coordination not state execution | Compatible | Unaffected; `ConversationManager` is not the proposed owner of this decision. |
| ADR-0005 — OS owns Tool Engine and Context Manager, Kernel stays domain-agnostic | At risk today, independent of this proposal | Already violated elsewhere (`kernel/aca_kernel/operations/basic.py`). This proposal does not worsen it if capability metadata moves to plugins as specified (§3.8), but would worsen it if operation names stay hardcoded in `aca_os/operational_*` files, repeating the existing violation instead of fixing it. |
| RFC-0001 — CSM is the only state representation, immutable, every operation produces a new version | Compatible | The proposed decision record is a derived, turn-scoped CSM projection, not a new state model. No independent Case State store is proposed (ACA-019 §6, reaffirmed here — the 100% projected-ranking benchmark result already demonstrates a persistent Case State is unnecessary). |

## 5. Compatibility With the Conversational Philosophy

The requester's framing — "la conversación sería únicamente la interfaz
visible de ese trabajo" — is not in tension with ACA's stated philosophy. It
*is* ACA's stated philosophy, verbatim, since before this specific
architectural question was ever raised:

> ACA no conversa para parecer inteligente. ACA conversa para realizar
> trabajo de servicio de forma inteligente, segura y auditable. (ACA-006 §1,
> citing the original ACA Vision & Work Model research)

So the philosophical claim is not new and should not be treated as a fresh
hypothesis needing validation — it was already accepted as a founding
motivation. What is unresolved is not philosophical, it is causal and
structural: the *runtime's* decision ordering does not yet reflect that
philosophy, because `ActionPlanner` selects before the richer conversational
and operational understanding exists. Reframing the question this way
matters for scope: it means option 1 ("la hipótesis es incorrecta") is too
dismissive — the philosophy is real and already adopted — but it also means
the fix is narrower than "the conversation is not the real model," which
would understate how much of ACA's existing conversational cognition
(`ConversationState`, `ConversationPlan`, `InformationGainPlan`,
`ConversationResponsePlan`) is legitimately load-bearing and should not be
subordinated to a new work layer. Conversation is the *interface*; it is
also still the *only* place ACA currently understands what the user needs,
and that does not change.

## 6. Why Option 2, Not Option 3 — the Semantic Authority Precedent

This repository already has a proven pattern for introducing exactly this
shape of change safely, used three times (`ConversationalAct`,
`ConversationalGoal`, and, differently, the Conversational-First response
path): introduce the new projection in shadow/observation mode first,
require it to prove parity or improvement against the existing path with a
dedicated benchmark, promote it through an atomic, rollback-capable selector
that never merges fields between old and new authority, and only then
consider retiring the old path. ACA-019's six-phase migration plan (§17 of
that document) is this exact pattern, independently arrived at for
operational work before the Semantic Authority work existed to prove it.

That precedent is direct evidence against building a new, separate layer
(option 3): the repository's own track record shows that the safe way to
introduce this kind of capability is by extending an existing authority
under a proven promotion discipline, not by adding a new one. It is also
evidence against concluding the hypothesis is simply wrong (option 1): the
gap ACA-019 identified is real, unaddressed, and independent of everything
built since.

## 7. Final Recommendation

**Do not implement anything now.** This document is, as requested, an
architecture review only.

If and when this work is picked up, it should resume exactly where ACA-019
left off, not restart:

1. Treat ACA-019 §17 (Phase 0 through Phase 6) as the migration plan. It
   remains valid; verify its Phase 0 baseline is still accurate (this
   document does that) and proceed from Phase 1.
2. Do not start Phase 1 before the plugin manifest consolidation identified
   in ACA-019 §10.3 (§3.8 of this document) — it is a hard prerequisite that
   was not previously sequenced explicitly enough.
3. Weigh this work against ACA-200's `START_REAL_WORLD_TESTING`
   recommendation before committing to it; they are not the same priority,
   and this document does not resolve which should come first.
4. Apply the single-authoritative-writer discipline from ACA-104 explicitly
   to the Candidate Work promotion, not just to Semantic Authority — the
   same failure mode is possible here and would be easy to reintroduce by
   assuming it only applies to the semantic firewall track.

No code, class, contract, or runtime change is proposed by this document.
