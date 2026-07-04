# Sprint 22 — Zero-Cost Flow Router

## Status

Completed.

## Goal

Introduce an explicit zero-cost routing layer between action planning and runtime execution.

Sprint 20 detects intent.
Sprint 21 converts intent into an action plan.
Sprint 22 converts the action plan into an execution flow.

## Design boundary

The Flow Router does not call tools, mutate memory, evaluate policy, or invoke LLMs.
It only maps deterministic `ActionPlan` objects into auditable `ExecutionFlow` objects.

## Runtime pipeline

```text
Event
  ↓
Conversation Manager
  ↓
Intent Matcher
  ↓
Action Planner
  ↓
Flow Router
  ↓
Policy Manager
  ↓
Tool Engine / Kernel
  ↓
Memory / Context / Output
```

## New module

`zero_cost/flow_router.py`

It provides:

- `ExecutionFlow`
- `FlowRouter`
- `DEFAULT_FLOW_ROUTES`

## Runtime integration

`ACAOSRuntime` now creates an execution flow after the action plan and stores it in:

```python
state.facts["zero_cost_execution_flow"]
```

The flow is also passed into the kernel execution context as `execution_flow`.

## Why this matters

The runtime no longer needs to grow decision logic directly.
Future behavior can be added as new routes and flows instead of embedding conditional logic inside the runtime.

This keeps ACA aligned with the zero-cost runtime philosophy:

- deterministic
- offline
- auditable
- LLM-independent
