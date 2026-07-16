# ACA-303 - Observability Completeness

Status: Implemented, observability only
Scope: ACA-302 Phase 2 ("Observability Completeness"), closing the gaps ACA-200 §9.3 and §12.4 identified
Runtime impact: none (no visible response, decision, or benchmark score changed)
Code impact: `aca_os/component_registry.py`, `aca_os/step_handlers.py`, `aca_os/runtime.py`, `aca_os/authority_dependency_graph.py`, `aca_os/introspection.py`, plus test updates
Depends on: ACA-200 (Core Readiness Audit), ACA-302 (Real-World Testing Roadmap), ACA-104 (FW-11 resolution)

## 1. Objective and Scope Discipline

ACA-302 Phase 2 named two concrete targets before `START_REAL_WORLD_TESTING`
(Phase 3) could produce trustworthy evidence:

1. register the components ACA-200 §12.4 found missing from the Component
   Registry (17 registered, omitting `SemanticAuthority`, `SemanticProjector`,
   both authority selectors, `RuntimeExecutor`, `LegacyRuntimeExecutor`, step
   handlers, Kernel, Composer, LLM providers);
2. correct the stale `ConversationalGoal` authority label ACA-200 §9.3 found
   in the Authority Graph generator.

This sprint executed both, plus the two adjacent checks the requester added:
that `RuntimeIntrospectionAPI` can fully reconstruct a turn, and that
Component Registry, Authority Dependency Graph, and Runtime Introspection
describe the same system. All changes are additive registration, metadata
correction, or summary extraction. No cognitive, routing, execution, or
output behavior was touched. `RuntimeExecutor`, `ConversationState`,
`SemanticAuthority`, `MissionManager`, `Kernel`, and `NarrativeResponseComposer`
were not modified — only referenced for read-only registration.

## 2. Components Added

### 2.1 Component Registry: 17 → 36

| # | Name | Class | How it was found missing |
| --- | --- | --- | --- |
| 1 | `kernel` | `ACAKernel` | Live `runtime.kernel` attribute, absent from `_runtime_component_specs()` |
| 2 | `compiler` | `GraphCompiler` | Live `runtime.compiler` attribute, same omission |
| 3 | `mission_manager` | `MissionManager` | Live `runtime.mission_manager` attribute, same omission |
| 4 | `semantic_authority` | `SemanticAuthority` | Lives on `runtime.conversation_manager.semantic_authority`, a nested path the generic spec-walk (`getattr(runtime, name)`) cannot reach |
| 5 | `semantic_projector` | `SemanticProjector` | Same nested-path reason |
| 6 | `conversational_act_authority_selector` | `semantic_authority_pilot.select_conversational_act_authority` | A function, not a class instance — no object to `getattr` at all |
| 7 | `conversational_goal_authority_selector` | `semantic_authority_pilot.select_conversational_goal_authority` | Same reason |
| 8 | `legacy_runtime` | `LegacyRuntimeExecutor` | Live `runtime.legacy_runtime` attribute, constructed after the registry existed, never registered |
| 9-16 | `step_handler_policy`, `step_handler_tool_lookup`, `step_handler_kernel`, `step_handler_memory`, `step_handler_context`, `step_handler_output`, `step_handler_handoff`, `step_handler_escalation` | `PolicyStepHandler`, `ToolLookupStepHandler`, `KernelStepHandler`, `MemoryStepHandler`, `ContextStepHandler`, `OutputStepHandler`, `HandoffStepHandler`, `EscalationStepHandler` | Live inside `runtime.step_handlers`, a private `_handlers` dict with no enumeration accessor |
| 17 | `runtime_executor` | `RuntimeExecutor` | **No persistent instance exists anywhere** — constructed fresh inside `_execute_runtime_executor_official` on every turn; registered as a static descriptor (`metadata: instantiation=per_turn`), not an instance |
| 18 | `narrative_response_composer` | `NarrativeResponseComposer` | Same reason — instantiated inline inside `OutputStepHandler.execute()`, never stored; also a static descriptor |
| 19 | `llm_verbalizer` | `LLMVerbalizer` | Lives on `runtime.step_handlers.resolve("output").llm_verbalizer`, three levels deep |

19 new components, `17 + 19 = 36`, confirmed by direct execution (`sdk.factory.build_galicia_runtime().component_registry.snapshot()["component_count"] == 36`).

### 2.2 Two categories of registration needed, both reused

- **Simple attributes** (`kernel`, `compiler`, `mission_manager`): added to
  `_runtime_component_specs()` in `component_registry.py` — the existing
  generic mechanism already used for 14 other components. No new mechanism.
- **Nested, functional, or non-instantiated components**: registered with the
  same guarded pattern (`if self.component_registry.get(name) is None: ...
  register_instance/register + initialize + activate`) `ACAOSRuntime.__init__`
  already used for `plugin_lifecycle` and the three `domain_pack_*`
  components. No new mechanism was invented; the existing precedent was
  extended to the components ACA-200 named.
- One small additive accessor was needed: `StepHandlerRegistry.all()`
  (`aca_os/step_handlers.py`), returning a copy of the private handler dict.
  This is the only new method added anywhere in this sprint; it changes no
  existing behavior and is required to enumerate step handlers without
  reaching into a private attribute.

## 3. Inconsistencies Corrected

### 3.1 ConversationalGoal's stale authority label (ACA-200 §9.3)

Before this sprint, the Authority Graph generator had a
`select_conversational_act_authority` transition edge (feeding
`ConversationalAct`) but **no equivalent edge for
`select_conversational_goal_authority`** — the goal selector's atomic
authority selection was invisible to the static generator entirely. The only
edge into `conversational_goal` was `apply_conversational_goal` reading
`user_text` with a hardcoded `legacy_primary` authority, so
`_effective_authority()` always returned `"legacy"` regardless of what the
runtime actually selected.

| Property | Before | After |
| --- | --- | --- |
| `conversational_goal.effective_authority` | `"legacy"` | `"semantic_pilot_with_parity_gate_else_legacy"` |
| `conversational_goal.owner` | `"conversation_state"` | `"semantic_pilot_or_legacy"` (matches `conversational_act`'s existing pattern) |
| Edge into `conversational_goal` from `select_conversational_goal_authority` | absent | present, `authority="semantic_conditional"`, mirroring the existing `conversational_act` edge exactly |
| `conversational_goal` in `recomputation_audit` | absent (never evaluated — `conversational_goal` was not even in the checked-artifact list) | `GUARDED_MULTI_AUTHORITY`, same classification already used for `conversational_act` |
| `conversational_goal` promotion readiness | `LOW_RISK` (status was already correct by coincidence, since it fell through to a different branch) | `READY`, with an explicit reason describing the actual parity-gate condition, matching the precedent set for `conversational_act` |

The fix required four changes, all in `aca_os/authority_dependency_graph.py`,
all mirroring an existing pattern already applied to `conversational_act`
rather than inventing a new one:

1. Added the missing `_TransitionSpec` for `select_conversational_goal_authority`.
2. Added an explicit `conversational_goal` case to `_effective_authority()`.
3. Added `conversational_goal` to the artifact list `_recomputation_audit()`
   checks for multi-producer patterns (it was never in that list at all —
   a second, more basic omission uncovered while fixing the first).
4. Generalized the `conversational_act`-only `"GUARDED_MULTI_AUTHORITY"`
   special case (in both `_recomputation_audit()` and `_promotion_readiness()`)
   to a shared `_GUARDED_MULTI_AUTHORITY_ARTIFACTS = ("conversational_act",
   "conversational_goal")` tuple, so future artifacts with the same atomic-
   selector-with-Legacy-rollback shape don't require re-deriving this fix a
   third time.

This is exactly the class of defect ACA-200 flagged as risk: *"Promotion
decisions can be made from stale metadata."* `ConversationalGoal` was already
correctly gated in the running code (per ACA-103/ACA-104); the Authority
Graph simply could not see it.

### 3.2 Naming variances documented, not changed

Cross-referencing every producer/consumer name in the Authority Graph's edges
against the Component Registry (§4) surfaced a few label mismatches that
refer to the same real component under different names:

| Authority Graph label | Component Registry name |
| --- | --- |
| `graph_compiler` | `compiler` |
| `legacy_runtime_executor` | `legacy_runtime` |
| `semantic_authority_pilot` (single label) | `conversational_act_authority_selector` + `conversational_goal_authority_selector` (two, finer-grained) |
| `*_step_handler` suffix (e.g. `output_step_handler`) | `step_handler_*` prefix (e.g. `step_handler_output`) |

These are cosmetic naming differences between two independently-evolved
generators, not authority discrepancies — unlike §3.1, nothing here claims a
different authority than what the runtime actually does. Renaming either
side was judged out of scope: it would touch many `_TransitionSpec` entries
for a labeling preference, not an observability defect, and risked exceeding
"correct only observability inconsistencies." Recorded here so a future
sprint does not need to re-discover it.

## 4. Consistency Verification: Registry, Graph, and Introspection Describe the Same System

Every producer/consumer name in the Authority Graph's 66 edges was checked
against the Component Registry's 36 entries. Every one resolves to exactly
one of:

- a registered component (16 of the graph's real, singular runtime
  components — action_planner, context_manager, conversation_manager,
  decision_graph_engine, flow_router, intent_matcher, kernel, llm_verbalizer,
  memory_engine, mission_manager, narrative_response_composer, policy_manager,
  runtime_executor, semantic_authority, semantic_projector, tool_engine —
  plus the naming variances in §3.2, also registered under their Registry
  name);
- the `runtime` orchestrator itself, which owns the registry and is not
  self-registered, matching how no other runtime-in-this-repository
  self-registers;
- an internal Kernel operation class (`kernel_extract`, `kernel_infer`,
  `kernel_plan`, `kernel_generate`) — sub-components of the already-registered
  `kernel`, not independently instantiable services;
- a data/state model (`conversation_state`) — not a service, correctly absent
  from a *component* registry;
- an explicitly Shadow-only or evaluation-only pseudo-producer
  (`operational_work_mapper`, `operational_governance_gate`,
  `operational_audit_ledger`, `evaluation_shadow`,
  `evaluation_or_tool_integration`, `candidate_ranking_shadow`,
  `legacy_conversational_act_adapter`, `plugin_semantic`,
  `conversation_manager_or_runtime`, `runtime_or_kernel_handler`) —
  correctly **not** registered as official components, per ACA-302 Phase 1's
  freeze list. Registering these would have misrepresented Shadow components
  as part of the official Runtime, which this sprint's mandate explicitly
  excluded ("no implementar nuevas capacidades").

No producer or consumer name in the Authority Graph refers to a component
that should be registered and is not. `RuntimeIntrospectionAPI.component_
inventory()` reads directly from `runtime.component_registry.list()`, so
completing the registry (§2) automatically completed introspection's
component inventory — no separate introspection change was needed for this
part.

## 5. RuntimeIntrospectionAPI: Turn Reconstruction Review

Reviewing what `_state_summary()`/`_trace_summary()` exposed against every
decision point in ACA-200 §3.1's official pipeline diagram found the
observability chain already covered: `IntentMatch`, `ActionPlan`,
`ExecutionFlow`, `ExecutionPlan`, `runtime_execution_engine` (official vs.
Legacy selection and comparison), `conversation_state_runtime` (semantic
shadow, semantic projection shadow, both authority-pilot decisions, CIM/plan
artifacts), and tool execution outcomes were all already present.

**One real gap was found:** the `output` step's `ExecutionStepOutcome`
already records a rich decision — whether the Composer changed the base
response and why, which conversational authority mode was used
(`legacy_response` vs. `conversation_first`), whether Conversational-First
rolled back and why, and the full LLM verbalization outcome (provider,
model, accepted/fallback, rejection reasons) — but nothing above
`execution_step_outcomes` ever surfaced it. `_tool_execution_summary()` walks
that same list but only extracts `result.tool_execution`, ignoring the
`output` step entirely. A turn could not be fully audited from
`_state_summary`/`_trace_summary` alone: *why* the visible response was what
it is (deterministic vs. LLM, rolled back or not) was invisible above the raw
trace.

Fixed with one additive function, `_output_decision_summary()`, added to
`aca_os/introspection.py` and wired into `_state_summary()["output_decision"]`.
It reads the existing `output` step outcome and surfaces `composer_changed_
response`, `composer_reason`, `conversation_authority`, and
`llm_verbalization` — no new data is computed, only exposed.

### Evidence: a real turn, fully reconstructed

```text
python -c "... runtime.process(Event(payload='Hola', ...)) ...
           snapshot = runtime.introspection.snapshot(state=state) ..."
```

```json
{
  "composer_changed_response": false,
  "composer_reason": "preserved_specialized_response",
  "conversation_authority": {
    "authority_mode": "legacy_response",
    "authority_reason": "conversational_first_disabled",
    "rollback_reason": null,
    "responses_equal": true
  },
  "llm_verbalization": {
    "accepted": false,
    "fallback_reason": "llm_disabled",
    "provider": "openai",
    "validation": { "rejection_reasons": ["llm_disabled"] }
  }
}
```

`snapshot.components` returned all 36 registered components for the same
turn. Combined with the already-present `last_state`/`last_trace` fields,
this turn's complete causal chain is now recoverable from one introspection
call: which authority selected `ConversationalAct`/`ConversationalGoal`
(`conversation_state_runtime`), which intent/action/flow/plan was chosen
(`intent`, `action_plan`, `execution_flow`, `execution_plan`), which executor
ran it and how it compared to Legacy (`runtime_execution_engine`), and now
*why the visible text is what it is* (`output_decision`) — the one link that
was previously missing.

## 6. Final State of Observability

| Question | Before ACA-303 | After ACA-303 |
| --- | --- | --- |
| Components registered | 17 | 36 |
| `SemanticAuthority`/`SemanticProjector` observable? | No | Yes |
| Authority selectors observable as components? | No | Yes (2) |
| `RuntimeExecutor`/`LegacyRuntimeExecutor` observable? | No / No | Yes / Yes |
| Step handlers observable individually? | No | Yes (8) |
| `Kernel`/`Compiler`/`MissionManager` observable? | No | Yes |
| `NarrativeResponseComposer`/`LLMVerbalizer` observable? | No / No | Yes / Yes |
| `ConversationalGoal` authority label accurate? | No (stale `"legacy"`) | Yes (`"semantic_pilot_with_parity_gate_else_legacy"`) |
| `ConversationalGoal` correctly classified as guarded multi-authority? | No (not even checked) | Yes, symmetric with `ConversationalAct` |
| Can a turn's visible-response reasoning (Composer/LLM/Conversational-First) be reconstructed from introspection alone? | No | Yes (`output_decision`) |
| Registry / Authority Graph / Introspection describe the same system? | Not verified; ACA-200 flagged this as unproven | Verified (§4): every real, singular, official component in the graph is registered; every non-registered producer is correctly a Shadow/pseudo/sub-component/state-model label |

## 7. Verification Evidence

| Check | Result |
| --- | ---: |
| Full test suite | 730 passed in 537.00s (0:08:57) |
| Focused suite (authority graph, firewall plan, FW migrations, component registry, CLI, domain packs, plugins, runtime API/CLI/REST, Studio) | 165 passed across two runs |
| Conversational-First benchmark | 9/9, 100%, unchanged |
| Semantic understanding benchmark | 98.65%, unchanged |
| Semantic adversarial benchmark | accuracy 70.72%, unchanged |
| Semantic projection benchmark | MATCH/DIFFERENT/EXTRA/MISSING distribution unchanged |
| `smoke_rc1.py` (5 scenarios) | Identical visible responses to the pre-ACA-303 run, byte-for-byte |
| Component registry snapshot | 36 components, all `state=active`, confirmed by direct execution |

No visible response, benchmark score, or hash changed. Three existing tests
were updated because they encoded the *old, incomplete* Authority Graph
state as if it were correct (exact promotion-order position, an exact
mermaid class-grouping string, and an exact non-overwrite record count) —
each updated with the newly accurate value and a comment explaining why,
following the same discipline used in ACA-104.

## 8. Impact on START_REAL_WORLD_TESTING (ACA-302 Phase 3)

ACA-302 explicitly sequenced Phase 2 before Phase 3 for one reason: running
real conversations through observability that ACA-200 itself proved could not
"prove which authority executed a turn" would repeat, in a new form, the
exact mistake ACA-024 already had to correct once (declaring/interpreting a
status the observability of the moment could not actually support). This
sprint removes that specific risk:

- A reviewer triaging a real conversation (the ACA-205/206/207 method this
  roadmap is built on) can now confirm, from one introspection snapshot,
  whether `ConversationalGoal` was selected semantically or by Legacy
  rollback with an accurate label — not a static one that always says
  `"legacy"` regardless of what happened.
- The same reviewer can now see, without instrumenting anything temporarily
  (as ACA-205/206 had to), whether a wrong visible response came from the
  Composer, from a Conversational-First rollback, or from the LLM — the
  `output_decision` field makes this a permanent, first-class introspection
  output instead of a one-off diagnostic.
- Every component that can execute in an official turn is now nameable and
  inspectable (`RuntimeExecutor`, step handlers, `Kernel`, `LLMVerbalizer`
  included), so future Studio/CLI/REST consumers of the registry no longer
  omit the components most relevant to diagnosing a real conversation.

ACA-302 Phase 3 (`START_REAL_WORLD_TESTING`) can now begin. Its own
prerequisites (Phase 0 git baseline, Phase 1 freeze list) remain open and are
unaffected by this sprint.
