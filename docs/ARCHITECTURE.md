# Architecture

ACA is a deterministic Cognitive Runtime.

LLMs are optional adapters. They are not part of the core runtime contract.

## Current runtime pipeline

```text
Input/Event
    │
    ▼
Conversation Manager
    │
    ▼
Intent Matcher
    │
    ▼
Action Planner
    │
    ▼
Flow Router
    │
    ▼
Execution Plan
    │
    ▼
Decision Graph Engine
    │
    ▼
Policy Manager
    │
    ▼
Tool Engine
    │
    ▼
Compiler
    │
    ▼
Kernel
    │
    ▼
Memory Engine
    │
    ▼
Context Manager
    │
    ▼
Output
```

## Dependency rule

Components do not depend on other components directly.

Allowed:

```text
Component
    │
    ▼
Runtime API
    │
    ▼
Runtime Services
    │
    ▼
Kernel
```

Forbidden:

```text
Component
    │
    ▼
Other Component
```

## Text normalization boundary

Text normalization is a framework-level contract exposed by `aca_core.text`.
Runtime services, Kernel components, plugins and public conversation layers must
use this API for natural-language input normalization.

The boundary is deterministic, idempotent, domain-agnostic and independent of
business plugins. Local accent maps, mojibake maps and wrapper functions that
only delegate to normalization are not allowed.

## Observability rule

Execution Trace is the source of truth.

Timeline is a simplified view generated from runtime state and runtime events.

Interfaces such as CLI, Studio, REST, or MCP must not contain business logic.
They render runtime contracts only.

## Runtime Intelligence layer

Runtime Intelligence capabilities produce deterministic analysis over runtime decisions.

Current capability:

- Decision Graph Engine

The Decision Graph Engine consumes existing runtime contracts:

- Intent Match
- Action Plan
- Execution Flow
- Execution Plan

It produces:

- `zero_cost_decision_graph`
- `DECISION_GRAPH` trace operation
- `runtime.decision_graph_created` event

It does not execute the runtime and does not control the Kernel.

## Conversation State contract

ACA defines a canonical `conversation_state.v1` contract in
`aca_os.conversation_state`. `ConversationManager` is now the operational owner
of that contract during each turn: it loads the current `ConversationState`,
projects it into the legacy `CognitiveState` runtime carrier, commits the final
state back to `ConversationState`, and records the mutations produced by the
turn.

Top-level ownership categories are:

- central state: focus, topic stack, active mission, goals, slots, confirmed
  facts, refuted facts, active hypotheses, relevant evidence, conversational
  strategy, pending questions, last conversational act, conversation summary
  and user signals;
- derived state: context bundles, planner outputs, supervisor outputs,
  execution plans, policy results and runtime projections;
- product state: public-demo counters, response category and UI/session
  helpers;
- temporary state: turn-scoped execution state;
- persistent state: conversation identity, turn count and future summaries.

Existing structures can project into or out of the contract:

- `ConversationState.from_cognitive_state(...)`;
- `ConversationState.to_cognitive_state(...)`;
- `PublicConversationState.to_conversation_state(...)`;
- `PublicConversationState.from_conversation_state(...)`;
- `ContextBundle.to_conversation_state(...)`;
- `ConversationManager.conversation_state(...)`.

`CognitiveState` remains the runtime compatibility carrier for Kernel,
Policy, Memory and Context. It is not the owner of conversation lifecycle data.
`PublicConversationState` remains a product-specific view. Mission logic stays
inside `MissionManager`, but mission data is loaded from and committed through
`ConversationState`.

Every runtime turn records `facts["conversation_state_runtime"]` with:

- the initial `ConversationState`;
- the final committed `ConversationState`;
- field-level changes and responsible components;
- projections generated during the turn.

## Slot lifecycle

ACA now resolves pending questions through `ConversationState` before normal
intent routing. Slots use the `slot_lifecycle.v1` contract:

- `pending`: the framework needs the answer.
- `partially_filled`: the user responded, but the value is ambiguous or not
  enough to close the question.
- `answered`: the user supplied a value that closes the pending question.
- `confirmed`: a previously answered value is explicitly confirmed.
- `invalidated`: the slot value is no longer usable for the current mission.
- `refuted`: the user rejects a previously accepted value.

Pending questions are projections over slots, not standalone text. Each pending
question records the target slot, reason, priority, related mission, prompt and
closure conditions.

At the beginning of a turn, `ConversationManager` loads `ConversationState` and
asks it to resolve pending slot answers from the new user message. If a slot is
resolved, the state is updated before intent, action, flow and execution-plan
selection. Slot resolution records `conversation_slot_resolution` with:

- slot detected;
- evidence used;
- confidence;
- lifecycle transition;
- resolved question;
- responsible component.

This is the first cognitive behavior change built on top of the operational
Conversation State owner. It still does not implement hypothesis revision,
contradiction handling, recap, strategy shifting or dynamic topic-stack
behavior.

## Conversational facts and mission advancement

ACA now assimilates user-provided information into explicit conversational
facts before response generation. The contract is `conversational_fact.v1`.
Each fact records:

- `type`;
- `value`;
- `origin`;
- `confidence`;
- `mission_type`;
- `acquired_turn`;
- `evidence`;
- `status`;
- `history`.

Fact state uses the `fact_lifecycle.v1` contract:

- `active`;
- `superseded`;
- `refuted`;
- `withdrawn`;
- `obsolete`.

Only one fact of a given type can be active in `confirmed_facts`. Older values
are archived either inside the active fact history or under `refuted_facts`
when no active replacement exists. This preserves traceability without letting
old values govern future decisions.

Slot resolution may detect a value, but fact assimilation owns the conversion
from that value into conversational knowledge. This keeps slot lifecycle and
knowledge assimilation separate: slots answer pending questions, while facts
govern subsequent cognition.

For the current auto-claim guidance mission, ACA can assimilate facts such as:

- `injuries = false`;
- `user_role = insured`;
- `claim_report_loaded = true`;
- `documentation_available = true`.

Mission state uses the `mission_lifecycle.v1` contract:

- `initialized`;
- `gathering_information`;
- `waiting_user`;
- `ready_to_progress`;
- `progressing`;
- `completed`;
- `suspended`.

When a new fact is assimilated, `ConversationState` evaluates the active
mission, updates mission facts, blockers, missing slots, lifecycle status and
`next_act`, then projects that updated mission into the runtime carrier. This
lets ACA stop asking for information that was already supplied and advance to
the next conversational act.

Each turn can expose:

- `conversation_fact_assimilation`: facts added or explicitly confirmed;
- `conversation_fact_revision`: facts replaced, refuted, withdrawn or left
  unresolved because the correction target was ambiguous;
- `conversation_mission_advancement`: previous mission state, new mission
  state, reason, considered facts and responsible component.

These traces are turn-scoped. They remain observable through runtime facts and
`conversation_state_runtime`, but they are not persisted as confirmed facts in
the next turn.

Correction handling runs before the main response. For example:

- `No hubo lesionados` followed by `Perdon, si hubo lesionados` refutes the
  previous `injuries = false` fact and activates `injuries = true`.
- `Soy asegurado` followed by `No, soy tercero` supersedes the active
  `user_role` fact.
- `La denuncia ya esta cargada` followed by `Perdon, todavia no` refutes
  `claim_report_loaded = true` and returns the mission to the report step.
- `Me confundi` withdraws the latest clearly associated fact; if multiple facts
  are equally plausible, ACA asks for clarification instead of inventing the
  target.


## Compiler and execution-plan alignment

The Runtime creates a deterministic `Execution Plan` before entering the Kernel.
The plan is the source of truth for program selection. It records both the
selected flow and the authorized `kernel_program`. The Compiler consumes that
program and must not reinterpret the original text when an execution plan is
present.

For example, `knowledge_lookup` selects the `knowledge_lookup` program and
`guided_process` selects `auto_claim_guidance` through the plan contract, not by
running another text classifier.

Tool results remain evidence. They are passed into Kernel operation context and
can be used by generation operations to produce a response, while the final
evidence is still recorded in Cognitive State, Context Bundle and Execution
Trace.

Policy may explicitly interrupt the plan for safety or escalation. Those cases
are recorded as `runtime_execution_authority.status = policy_interrupted`.
If a planned kernel program is unavailable, the compiler may use a controlled
fallback and the authority record must expose that modification.

## Policy plan alignment

Policy is an authorization boundary, not a parallel classifier. When a valid
`ExecutionPlan` exists, `PolicyManager` consumes the plan and validates the
planned action:

- `knowledge_lookup` authorizes a planned `tool_lookup` and validates the
  planned `tool_key`.
- `guided_process`, `static_response`, `fallback` and `clarification` are
  allowed unless an explicit policy restriction applies.
- `safe_escalation` and `human_handoff` are explicit policy interruptions.

Policy may still use legacy text inspection only when no valid execution plan is
available. Any policy modification must be recorded in `PolicyResult` and
projected into `runtime_execution_authority`.

## Execution step outcomes

`ExecutionPlan.steps` are declarative. The current runtime still executes them
through manual orchestration, but each planned step now produces an
`ExecutionStepOutcome` record.

An outcome records:

- step name;
- executor component;
- started and finished timestamps;
- duration;
- status: `success`, `skipped`, `interrupted` or `error`;
- result data;
- evidence;
- cognitive state changes;
- controlled errors;
- interruptions.

Outcomes are stored in `state.facts["execution_step_outcomes"]` and projected
through the runtime timeline as `EXECUTION_STEP_OUTCOMES`. This is not a logging
system. It is the cognitive audit contract that allows a future RuntimeExecutor
to execute plan steps directly without changing the observable shape.

## Runtime step handler contracts

Runtime step execution is now separated from runtime orchestration through
step-handler contracts:

```text
ExecutionPlan.step
    │
    ▼
StepHandlerRegistry
    │
    ▼
StepHandler
    │
    ▼
StepExecutionResult
    │
    ▼
ExecutionStepOutcome
```

`ACAOSRuntime` still owns the execution order. It explicitly resolves handlers
for `policy`, `tool_lookup`, `kernel`, `handoff`, `escalation`, `memory`,
`context` and `output`, but the step-specific execution logic lives behind
`StepHandler` contracts.

The handler layer introduces:

- `StepExecutionContext`: bounded input for a handler.
- `StepExecutionResult`: internal execution result.
- `StepHandler`: one executor per step type.
- `StepHandlerRegistry`: deterministic step-to-handler resolution.

Handlers execute. They do not make cognitive routing decisions. The plan and
policy remain the sources of decision and authorization.

## RuntimeExecutor shadow mode

ACA now includes a first plan-driven `RuntimeExecutor` in shadow mode. It walks
`ExecutionPlan.steps`, resolves each step through `StepHandlerRegistry`,
executes the corresponding handler and builds a parallel execution projection.

The official execution path is still `ACAOSRuntime.process`. Shadow mode does
not replace runtime orchestration, does not change user-visible behavior and
does not own final state. Its responsibility is comparison.

Each processed event records `state.facts["runtime_executor_shadow"]` with:

- official runtime projection;
- shadow executor projection;
- step order;
- handlers used;
- step statuses;
- interruptions;
- evidence;
- selected program;
- response;
- observable final state summary;
- explicit divergences.

Policy validation is treated as the mandatory authorization boundary after plan
creation. When a plan does not include a `policy` step, the shadow executor
evaluates policy for comparison but does not add a synthetic step outcome. This
keeps fallback/static flows compatible with the existing `ExecutionPlan` shape
while still comparing the same policy decision observed by the official runtime.

RuntimeExecutor shadow mode is a migration validator. Any divergence is recorded
instead of being silently reconciled.

## Tool execution boundary

Tool usage is split into two contracts:

- `ExecutionPlan` decides that a tool step is part of cognition.
- `ToolExecutionContract` decides whether and how the tool can run in a given
  execution mode.

Tool execution ownership is:

```text
ExecutionPlan
    |
    v
RuntimeExecutor
    |
    v
ToolLookupStepHandler
    |
    v
ToolEngine
    |
    v
ToolAdapter
```

`ACAOSRuntime` does not execute tool adapters directly. For flows that are not
fully migrated yet, the classic runtime may delegate only the planned tool step
to `RuntimeExecutor` and then continue the remaining imperative path with the
evidence produced by that step. This removes the legacy pre-execution route
without forcing full migration of `knowledge_lookup`.

Each tool adapter must declare:

- whether execution is deterministic;
- whether it has side effects;
- whether it supports dry-run;
- whether it supports replay;
- whether it supports shadow execution;
- its idempotency guarantee.

Tool calls receive a `ToolExecutionContext` with mode, origin, execution plan,
runtime engine, permissions, simulation config, existing evidence and replay
evidence.

Supported modes are:

- `official`;
- `shadow`;
- `dry_run`;
- `replay`;
- `simulation`.

In shadow mode, unsafe tools are not re-executed by accident. The tool engine
chooses the safest available action from the declared contract:

- reuse of existing evidence when available;
- direct execution only when the contract allows safe shadow execution;
- dry-run;
- replay;
- controlled rejection.

The current `StaticKnowledgeAdapter` is deterministic, side-effect free,
idempotent and safe for shadow mode. Future adapters that write databases, send
emails, call external APIs or mutate real systems must declare explicit dry-run,
replay or idempotency guarantees before they can participate safely in shadow or
simulation.

Each tool outcome records a `tool_execution_record.v1` with execution mode,
decision, reason, whether the tool actually ran and the contract used. Runtime
introspection exposes a flattened `tool_executions` summary for regression
detection without reading code.

## RuntimeExecutor controlled adoption

The controlled adoption path delegates selected flows to `RuntimeExecutor`:

- `fallback`;
- `guided_process`;
- `human_handoff`;
- `knowledge_lookup`;
- `safe_escalation`;
- `static_response`.

Slice 1 migrated simple response flows: `fallback` and `static_response`.
Slice 2 migrated `guided_process`, validating a full cognitive chain with
policy validation, kernel execution, memory, context and output.
Slice 3 migrated `knowledge_lookup`, validating a complete tool-backed
cognitive flow where `RuntimeExecutor` owns `tool_lookup`, `kernel`, `memory`,
`context` and `output`.
Slice 4 migrated policy interruptions: `human_handoff` and `safe_escalation`.
For those flows, Policy remains the authorization/interruption origin, while
`RuntimeExecutor` is the official engine that executes `handoff` or
`escalation`, then memory, context and output.

For migrated flows, `RuntimeExecutor` is the official execution engine.
`LegacyRuntimeExecutor` is still executed as an isolated validation projection
and is compared against the official result. It does not own final state and
does not write persistent runtime memory.

For every non-migrated flow, `LegacyRuntimeExecutor` remains the official
compatibility engine and `RuntimeExecutor` continues to run in shadow mode.
`ACAOSRuntime.process` no longer contains the legacy business execution path:
it builds the cognitive pipeline, selects the engine, coordinates comparison,
consolidates results and exposes observability.

Each execution records `state.facts["runtime_execution_engine"]` with:

- official engine;
- validation engine;
- selection reason;
- flow;
- kernel program;
- official tool execution ownership and action;
- interruption type, origin component, execution engine and result;
- comparison availability;
- equivalence score and percentage;
- divergence count and divergence details.

This keeps the migration explicit and reversible while preventing a second
hidden runtime architecture from emerging.

## Legacy Runtime isolation

`LegacyRuntimeExecutor` is the explicit boundary for remaining pre-adoption
execution. It contains the compatibility implementation for flows that have
not yet migrated to `RuntimeExecutor` and the validation projection used to
compare migrated flows.

The intended temporary split is:

```text
ACAOSRuntime
  -> builds Event -> Intent -> Action -> Flow -> ExecutionPlan -> Policy
  -> selects official engine
  -> coordinates comparison
  -> records trace and introspection

RuntimeExecutor
  -> official engine for migrated flows

LegacyRuntimeExecutor
  -> official compatibility engine for clarification
  -> validation projection for migrated flows
```

The remaining legacy-dependent flow is `clarification`. Once its role is
resolved and migrated or absorbed, `LegacyRuntimeExecutor` and its
kernel/finalization compatibility code can be removed without changing the
public runtime orchestration contract.

## Metrics Engine

Metrics Engine is a passive runtime service. It derives counters, gauges, histograms and component metrics from Execution Trace. Execution Trace remains the source of truth; Timeline remains a simplified view. Interfaces must consume metrics through the Runtime API and must not calculate observability state themselves.


## Studio Evolution

ACA Studio is a read-only Runtime Intelligence interface. It consumes the Runtime Introspection API and renders normalized panels for Runtime Health, Decision Graph, Metrics, Component Registry, Timeline, Trace and Event Bus.

Studio is not allowed to own runtime behavior. It only projects already-observed runtime contracts.


## Epic 3 — Plugin SDK Boundary

Plugins are external capabilities. They do not become runtime internals and they do not depend on components directly.

The first stable contract is the Plugin Manifest:

```text
Plugin
  │
  ▼
Plugin Manifest
  │
  ▼
Plugin Contract
  │
  ▼
Component Registry
  │
  ▼
Runtime API
```

A plugin must declare its name, version, runtime compatibility, entrypoint, capabilities, permissions, hooks, dependencies, tags and metadata before any future loader can execute it.

Sprint 35 intentionally does not import plugin code. It only validates the manifest and projects it into runtime-visible metadata.


## Sprint 36 — Plugin Loader

The Plugin Loader is a Runtime Service that discovers `plugin.json` manifests, validates them through the Plugin Manifest contract and registers plugin capabilities in the Component Registry.

It does not import plugin entrypoints and does not execute plugin code. This preserves deterministic loading and keeps Plugin SDK lifecycle execution separate from manifest discovery.

```text
Plugin Directory
  │
  ▼
plugin.json
  │
  ▼
PluginLoader
  │
  ▼
PluginContract
  │
  ▼
ComponentRegistry
```

Interfaces such as Studio, REST, CLI and MCP must observe loaded plugins through Runtime APIs and registry snapshots, not through plugin implementation modules.

## Sprint 37 — Plugin Validator

ACA validates plugins before they enter the Runtime-visible Component Registry.

```text
Plugin Manifest
      │
Plugin Validator
      │
Plugin Loader
      │
Component Registry
      │
Runtime API
```

Validation is deterministic and metadata-only. The validator checks runtime compatibility, safe entrypoints, hook targets, permission allowlists and registry dependencies without importing plugin code.


## Sprint 38 — Plugin Lifecycle

The Plugin Lifecycle Manager owns Runtime-visible plugin state after manifests are loaded and validated. It does not import or execute plugin entrypoints. It only coordinates deterministic lifecycle transitions and mirrors safe states into the Component Registry.

```text
Plugin Loader
      │
      ▼
Plugin Lifecycle Manager
      │
      ▼
Component Registry
      │
      ▼
Runtime API
```

Supported lifecycle states are `registered`, `initialized`, `active`, `paused`, `stopped`, `unloaded` and `failed`. Invalid transitions are rejected and recorded as lifecycle events.

This gives future Plugin SDK execution hooks a stable control plane without moving plugin behavior into the Runtime Core.
