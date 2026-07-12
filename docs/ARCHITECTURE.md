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

## Conversational act recognition

Before intent matching, ACA recognizes the conversational act of the incoming
turn through `ConversationState`. This is not a replacement for intent
matching. Intent matching still decides domain intent; conversational-act
recognition decides what the user is doing inside the conversation.

The contract is `conversational_act.v1`. Each act records:

- `act`;
- `confidence`;
- `evidence`;
- `component`;
- `turn`;
- `reason`;
- `target`;
- `impact`;
- `alternatives`.

Supported act types are:

- `pending_answer`;
- `confirmation`;
- `negation`;
- `correction`;
- `clarification`;
- `clarification_request`;
- `topic_shift`;
- `continuation`;
- `recap_request`;
- `simplification_request`;
- `deepening_request`;
- `closing`;
- `new_information`;
- `unknown`.

The selected act is stored as `ConversationState.last_conversational_act` and
projected into the runtime as `facts["conversation_act"]`. The full
turn-scoped recognition trace is projected as
`facts["conversation_act_recognition"]` and exposed through
`conversation_state_runtime`.

The act influences the next cognitive phases without becoming a second intent
classifier:

- pending answers guide slot resolution;
- correction acts guide fact revision;
- continuation and response-shaping acts preserve the active mission instead
  of restarting the flow;
- recap, simplification, deepening and topic-shift requests create explicit
  conversational goals before response generation.

## Conversational goals and strategy application

Recognizing an act is not enough. ACA converts each recognized act into a
`conversational_goal.v1` contract before entering the Kernel. The cycle is:

```text
ConversationalAct
  -> ConversationalGoal
  -> Strategy
  -> Response
  -> Fulfillment evaluation
```

Each goal records:

- originating act;
- conversational intention;
- selected strategy;
- success criteria;
- abandonment criteria;
- priority;
- expected mission impact;
- evidence used;
- fulfillment status.

Supported strategies are:

- `respond`;
- `simplify`;
- `deepen`;
- `summarize`;
- `continue`;
- `repair`;
- `switch_topic`;
- `close`;
- `ask_clarification`.

`ConversationState` owns goal creation. The Kernel consumes the generated
strategy and response plan; it should not independently infer what a
`simplification_request`, `recap_request` or `topic_shift` means.

The active goal is projected as `facts["conversation_goal"]`. At turn commit,
`ConversationManager` evaluates fulfillment against the generated response and
updates the same goal trace with:

- `satisfied`;
- fulfillment status;
- strategy checks;
- whether a second attempt is needed;
- whether strategy should change.

This Sprint does not introduce advanced strategy repair, hypothesis revision or
multi-step conversational planning. It makes strategy application explicit and
observable for the acts ACA already recognizes.

## Conversational focus and topic stack

ACA operationalizes conversational focus through `topic_stack.v1`, owned by
`ConversationState` and managed by `ConversationManager` at the beginning of
each turn. The stack is not a loose `active_topic` string: each entry is a
`conversation_topic.v1` object with:

- `id`;
- `type`;
- associated mission type and mission goal;
- associated conversational goal;
- priority;
- lifecycle status;
- creation turn;
- last active turn;
- associated facts;
- associated slots;
- short operational summary.

Topic lifecycle states are:

- `active`;
- `suspended`;
- `resumed`;
- `completed`;
- `abandoned`.

The stack supports explicit focus transitions:

- starting a mission creates or updates the active mission topic;
- a new-topic request suspends the active topic and creates an unresolved topic;
- return requests such as `volvamos a la denuncia` resume the matching
  suspended topic;
- indirect references such as `sobre lo anterior` resolve to a suspended topic
  when there is enough evidence;
- continuation requests such as `seguimos` resume the suspended mission topic
  when the active topic is an unresolved interruption.

Each transition is projected as `facts["conversation_topic_stack"]` and exposed
through `conversation_state_runtime`. The trace records the active topic,
suspended topic, resumed topic, transition reason, ambiguity when present, and
the updated topic summary.

Kernel response planning consumes the active topic summary from the
conversational-goal response plan. Recap requests summarize the operational
topic summary instead of reconstructing the whole conversation from raw turns.

## Conversational response quality

ACA decomposes user turns through `conversational_intent_model.v1` before
building the response plan. This is a pragmatic comprehension layer, not a
replacement for Intent Matching. Intent Matching still selects domain intent;
the conversational intent model describes what the user is trying to resolve in
the conversation.

The intent model records:

- `explicit_questions`: what the user literally asked or stated;
- `implicit_questions`: practical questions implied by that utterance;
- `dominant_concern`: the concern ACA should address first;
- `user_goal`: what the user is trying to accomplish;
- `user_assumptions`: assumptions suggested by the wording;
- `missing_information`: facts still needed before making stronger claims;
- `response_objective`: what the response should accomplish.

For example, `Puedo arreglar el auto?` is modeled as:

- explicit question: whether the car can be repaired;
- implicit question: whether repairing it could affect the claim;
- dominant concern: preserving the claim while needing the vehicle;
- missing information: authorization status and damage evidence;
- response objective: reduce uncertainty and explain how to preserve evidence.

ACA then builds a `conversational_response_plan.v1` before response generation.
The plan is owned by `ConversationState` and projected to the Kernel as
`facts["conversation_response_plan"]`. It does not replace Intent, Action,
Flow, Mission or Topic Stack; it decides how the response should prioritize the
user-facing need using the conversational intent model as input.

Before the response plan is finalized, ACA builds an `information_gain_plan.v1`.
This plan separates missing information from useful clarification. The
framework may know several facts are missing, but it only selects a user-facing
question when the answer can change a decision or unblock the next cognitive
step.

The information-gain plan records:

- `candidate_questions`: all clarification candidates considered for the turn;
- `expected_information_gain`: decision value of the selected question;
- `affected_decisions`: decisions that depend on the selected answer;
- `estimated_cost`: conversational cost of asking it;
- `blocking_level`: whether the missing information blocks progress;
- `clarification_priority`: deterministic cost/benefit score;
- `selected_question`: the single question ACA should ask now, if any.

`ConversationalResponsePlan` consumes this selection and exposes only the
chosen clarification in `required_information`. The Kernel must not rank or
choose between missing facts; it only renders the selected question with its
recorded purpose. If no candidate changes the current decision enough, ACA
answers with the information already available and asks nothing.

After Information Gain, ACA builds a persistent `conversation_plan.v1`. This is
the dynamic conversational plan for the active turn. It does not replace the
mission lifecycle or the Runtime `ExecutionPlan`: the mission still describes
the domain objective, and the `ExecutionPlan` still governs runtime execution.
`ConversationPlan` decides how the conversation should continue when new
evidence changes the path.

The conversation plan records:

- `active_plan`: ordered operational steps for the active mission/topic;
- `completed_steps`: steps already satisfied by facts, slots or prior turns;
- `pending_steps`: steps still needed;
- `abandoned_steps`: previously pending steps no longer present after
  replanning;
- `replanning_reason`: why the plan changed or remained valid;
- `inserted_steps`: temporary side steps such as answering a lateral question;
- `skipped_steps`: questions or steps avoided because new evidence made them
  unnecessary or lower value;
- `conversation_progress`: completed-step ratio and mission progress.

`conversation_plan.v1` is intentionally persistent across turns. At the start
of a new turn, ACA compares the previous plan with the new plan after slot
resolution, fact assimilation, topic handling and Information Gain. This makes
replanning auditable:

- if the user answers two pending questions in one sentence, both steps become
  completed;
- if the user says `ya cargue todo`, report/documentation questions are skipped
  because the facts are already available;
- if the user asks a lateral question such as `cuanto tarda normalmente`, ACA
  inserts a side step, answers it, and preserves the main pending step.

The Kernel must not reorganize conversational steps. It receives the updated
conversation plan through `facts["conversation_plan"]` and the response plan
through `facts["conversation_response_plan"]`.

After the Kernel generates the response, `ConversationManager` asks
`ConversationState` to evaluate `conversation_fulfillment.v1`. This closes the
deterministic conversational loop:

```text
ConversationalIntentModel
  -> InformationGainPlan
  -> ConversationPlan
  -> ConversationalResponsePlan
  -> Response
  -> ConversationFulfillment
  -> ConversationState
```

The fulfillment contract records:

- `fulfilled_goal`: whether the turn objective was fulfilled, partially
  fulfilled, not fulfilled, or failed;
- `fulfilled_steps`: plan steps or response objectives satisfied by the turn;
- `pending_steps`: steps still waiting after the response;
- `failed_steps`: expected steps the user did not satisfy;
- `recovery_actions`: deterministic next action such as resume, continue,
  reask/reformulate or close;
- `fulfillment_confidence`: deterministic confidence score;
- `completion_reason`: why the turn is considered fulfilled, partial or failed.

Fulfillment evaluation is not performed by the Kernel. The Kernel produces the
response; `ConversationState` evaluates whether that response satisfied the
plan. For example:

- `Cuando me van a contactar?` can close the objective if the response answers
  the process-progress concern and no blocking clarification remains;
- `No hubo lesionados` partially fulfills the turn, completes the injuries
  step, and leaves role confirmation pending;
- if ACA asked about injuries and the user answers something unrelated, the
  injuries step is marked failed and recovery selects reask/reformulate;
- if ACA answers a lateral timing question, fulfillment records the side step
  as satisfied and selects `resume_main_plan`.

The fulfillment trace is projected as `facts["conversation_fulfillment"]` and
included in `conversation_state_runtime`. It remains introspection-only and is
not exposed as user-facing text.

The response plan records:

- `primary_user_need`;
- `secondary_needs`;
- `dominant_concern`;
- `information_gain_plan`;
- `conversation_plan`;
- `response_priority`;
- `next_action`;
- `required_information`;
- `unresolved_questions`.

Response planning follows two conversational quality principles:

- Cognitive opacity: internal decisions such as strategy changes, topic
  suspension, avoidance of repetition, or mission mechanics remain available in
  introspection but must not be exposed as user-facing text.
- Question justification: every question ACA asks must have a recorded purpose,
  and when natural the response should expose that purpose to the user.

The expected response order is:

1. acknowledge the dominant user concern;
2. answer the primary need;
3. explain the reason briefly;
4. ask only the next useful question or indicate the next concrete step.

For example, when the user says `No se si mande las fotos, pero lo que mas me
preocupa es si puedo arreglar el auto`, ACA prioritizes the repair concern
before the secondary photo-upload concern, then asks any required mission
question with a purpose.

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

## Benchmark-driven consolidation candidates

The cognitive benchmark is now the gate for conversation-quality changes. It
currently shows that these contracts provide direct observable value:

- `conversation_intent_model`
- `conversation_information_gain_plan`
- `conversation_response_plan`
- `conversation_plan`
- `conversation_fulfillment`
- slot, fact assimilation and fact revision traces

It also flags two consolidation candidates that must not be removed yet:

- `conversation_goal`: currently useful for act strategy observability, but much
  of the user-visible behavior is carried by `conversation_response_plan` and
  `conversation_fulfillment`.
- `zero_cost_execution_flow` plus `zero_cost_execution_plan`: both remain useful
  as migration-era projections, but their separation should be revalidated once
  RuntimeExecutor migration debt is fully closed.

These are candidates only. No contract should be removed until the benchmark
proves that conversation behavior and introspection remain equivalent.
