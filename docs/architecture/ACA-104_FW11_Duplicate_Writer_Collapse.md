# ACA-104 - FW-11 Duplicate Writer Collapse

Status: Implemented
Masterplan package: `FW-11`
Effective scope: `ConversationIntentModel`, `InformationGainPlan`, `ConversationPlan`, `ConversationResponsePlan`
Visible response influence: None

## 1. Problem

`ConversationIntentModel`, `InformationGainPlan`, `ConversationPlan` and
`ConversationResponsePlan` were each computed twice per turn:

```text
ConversationManager.begin_turn (before MissionManager runs)
    -> ConversationState.model_conversational_intent(event.payload)
    -> ConversationState.plan_information_gain(event.payload)
    -> ConversationState.plan_conversation(event.payload)
    -> ConversationState.plan_conversational_response(event.payload)

ACAOSRuntime.process (after MissionManager.before_kernel runs)
    -> ConversationState.model_conversational_intent(event.payload)
    -> ConversationState.plan_information_gain(event.payload)
    -> ConversationState.plan_conversation(event.payload)
    -> ConversationState.plan_conversational_response(event.payload)
```

The second write always silently overwrote the first
(`CognitiveState.facts` keys are unconditionally replaced by
`ConversationState.to_cognitive_state`). ACA-100 flagged this as the
principal blocker for promoting `ConversationIntentModel` and named it
`FW-11`.

## 2. Evidence gathered before removing anything

Before removing the first write, an observation-only instrumentation module
(`aca_os/fw11_recomputation_evidence.py`) diffed both writes on every real
turn without changing behavior (`decision_influence: false`,
`state_mutation: false` on every record). Across the `smoke_rc1.py`
scenarios and the full test suite:

* every difference between the two writes was fully explained by
  `MissionManager` assigning `active_mission` in between them
  (`unexplained_variance_artifacts` was empty on every observed turn --
  no nondeterminism was ever found);
* `ConversationIntentModel`, `ConversationPlan` and
  `ConversationResponsePlan` are read directly by
  `NarrativeResponseComposer` (`_trace_payload`); the second write was
  always the one that reached it.

Separately, every known consumer of these four artifacts was checked by
direct source inspection:

| Consumer | Reads these 4 artifacts? |
| --- | --- |
| `MissionManager.before_kernel` | No |
| `PolicyManager.evaluate` | No |
| `zero_cost` (`IntentMatcher`, `ActionPlanner`, `FlowRouter`, `DecisionGraphEngine`) | No |
| `ACAOSRuntime._intent_from_conversation_act` / `_intent_from_slot_resolution` | No (only `active_mission`, `slots`, `conversational_act`) |
| `NarrativeResponseComposer` | Yes, from `CognitiveState.facts` after the turn finishes |
| `operational_work_mapper.map_operational_work` | Yes, but only via `evaluation.py` against an already-finished state (shadow, not live) |
| `public_conversation_product_layer` | Yes, but only after calling `runtime.process(...)` and reading its final result |

No component reads these artifacts between `ConversationManager.begin_turn`
and the post-Mission write. The first write had no consumer.

## 3. Change

The premature write was removed from `ConversationManager.begin_turn`
(`aca_os/conversation_manager.py`). The post-Mission write in
`ACAOSRuntime.process` (`aca_os/runtime.py`) is now the single authoritative
computation for all four artifacts.

The four audit-trail projection-log entries `begin_turn` used to record
(`conversational_intent_decomposition`, `information_gain_planning`,
`dynamic_conversation_planning`, `conversation_response_planning`) are still
recorded, now via `ConversationManager.record_conversation_planning_projection`,
called from `ACAOSRuntime.process` right after the single write completes.
`runtime_record["projections"]` still contains the same reason strings as
before; their field values now reflect the correct, mission-aware
computation instead of the discarded pre-Mission one.

`ConversationTurnContext` no longer carries `conversational_intent_model`,
`information_gain_plan`, `conversation_plan`, `conversational_response_plan`
or the instrumentation-only `conversation_state_before_planning` field --
nothing outside `aca_os/conversation_manager.py` read them.

Nothing in `ConversationState`, `MissionManager`, `NarrativeResponseComposer`,
or the rest of `ACAOSRuntime.process` changed.

## 4. Instrumentation disposition

`aca_os/fw11_recomputation_evidence.py` is kept as a standalone diagnostic
module, not wired into production. Its diff/origin/impact utilities are
generic and documented as reusable for future duplicate-writer
investigations (e.g. `intent_match` under `FW-12`). It is not imported by
`aca_os/runtime.py` or `aca_os/conversation_manager.py`; `ExecutionTrace` and
`conversation_state_runtime` no longer expose an `fw11_recomputation_evidence`
field.

## 5. Graph and plan delta

| Metric | Before FW-11 | After FW-11 | Delta |
| --- | ---: | ---: | ---: |
| inventoried text accesses | 37 | 33 | -4 |
| firewall violations | 30 | 26 | -4 |
| BLOCKER-severity consumers | 16 | 12 | -4 |
| recomputation records | 8 | 4 | -4 |
| `RECOMPUTED_AND_OVERWRITTEN` records | 4 | 0 | -4 |
| `ConversationIntentModel` status | BLOCKED (recomputed) | HIGH_RISK (still 2 critical free-text reads) | improved |
| `ConversationIntentModel` `recomputed` flag | true | false | resolved |

`ConversationIntentModel` remains `HIGH_RISK`, not `READY`: it still has two
critical free-text dependencies (`aca_os/conversation_state.py:model_conversational_intent`
and `aca_os/runtime.py:ACAOSRuntime.process`). That is `FW-10`'s remaining
scope, not `FW-11`'s. `InformationGainPlan`, `ConversationPlan` and
`ConversationResponsePlan` remain `BLOCKED` by design -- they are meant to
stay derived planner/response output and never become semantic authority
targets; only their duplicate write is gone.

Current fingerprints:

| Artifact | Hash |
| --- | --- |
| authority source | `a05cf43c87f2abe1e5d41a52d838959dd6ef43e22b2ea6b6ff30393fd54a402a` |
| authority graph | `10de08fe362611602e6c056b025e684ccabf079b551d02b1e88dd2874946f050` |
| firewall plan | `7d39b00448f363ec85bb648ce0300ab06b99251870ba54e448e551674b462f49` |

## 6. Compatibility and tests

No response template, planner, mission rule, slot lifecycle, topic
lifecycle, fact lifecycle, RuntimeExecutor path, Kernel path, Policy,
Governance, Ledger, Composer, Verbalizer, plugin, or benchmark fixture
changed.

Focused coverage verifies:

* `ConversationManager.begin_turn` no longer writes any of the four
  artifacts into `derived_state`;
* the single post-Mission write still reaches the composer with real,
  mission-aware data (`active_plan.current_step` populated);
* the audit-trail projection-log entries are still produced;
* the authority dependency graph no longer reports a
  `RECOMPUTED_AND_OVERWRITTEN` record for any of the four artifacts, and
  `promotion_readiness[...]["recomputed"]` is `false` for all of them;
* the removed instrumentation no longer appears in `ExecutionTrace` or
  `conversation_state_runtime`.

Validation:

| Check | Result |
| --- | ---: |
| focused FW-11 and adjacent suites (authority graph, firewall plan, FW migrations, conversation manager, dynamic planning, conversational-first, narrative composer, runtime integration) | 88 passed |
| conversational-first benchmark | 9/9, 100%, unchanged |
| semantic understanding benchmark | 98.65%, unchanged |
| semantic adversarial benchmark | 70.72%, unchanged |
| complete repository suite | see ACA-104 validation log (run after this document) |

## 7. Remaining blockers and next candidate

Twenty-six violations remain, twelve of them `BLOCKER` severity, concentrated
in `ConversationIntentModel`'s remaining free-text reads (`FW-10`), intent
routing (`FW-12`), Mission (`FW-14`) and Policy (`FW-15`). `FW-11`'s own
completion does not by itself make `FW-10` safe to attempt: `ACA-200`'s
`START_REAL_WORLD_TESTING` recommendation still stands, and no automatic
promotion is authorized by this document.
