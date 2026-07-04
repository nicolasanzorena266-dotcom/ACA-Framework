# Sprint 31 — Decision Graph Engine

## Status

Completed.

## Objective

Introduce a deterministic Decision Graph Engine as the first Runtime Intelligence capability.

The engine makes the runtime decision path explicit and observable without changing execution behavior.

## Scope

Added:

- `zero_cost/decision_graph.py`
- `DecisionGraphEngine`
- `DecisionGraph`
- `DecisionNode`
- `DecisionEdge`
- Runtime integration through `ACAOSRuntime`
- `DECISION_GRAPH` cognitive-state operation
- `runtime.decision_graph_created` event bus event
- Execution Trace component mapping
- Runtime introspection inventory entry
- DX inspection and doctor path awareness
- Unit and integration tests

## Architecture decision

Decision Graph Engine is a Runtime Intelligence capability, not a Kernel feature.

It consumes Runtime API contracts:

- Intent Match
- Action Plan
- Execution Flow
- Execution Plan

It produces an auditable graph:

```text
input.intent
    │
    ▼
plan.action
    │
    ▼
route.flow
    │
    ▼
execution.plan
```

The graph is declarative. It does not execute tools, mutate components, or control the Kernel.

## Runtime facts

Each process run now persists:

- `zero_cost_decision_graph`

Existing facts remain compatible:

- `zero_cost_action_plan`
- `zero_cost_execution_flow`
- `zero_cost_execution_plan`

## Observability

Execution Trace now includes:

- `DECISION_GRAPH`

Event Bus now emits:

- `runtime.decision_graph_created`

## Validation

Full suite executed successfully:

```text
89 passed
```
