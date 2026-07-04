# Sprint 21 — Zero-Cost Action Planner

## Status

Completed.

## Goal

Add the first deterministic planning layer after the zero-cost intent matcher.

Sprint 20 detects intent. Sprint 21 converts that intent into an auditable action directive without using LLMs, embeddings, remote APIs, or paid services.

## Runtime position

```text
Event
  ↓
Conversation Manager
  ↓
Intent Matcher
  ↓
Action Planner
  ↓
Mission Manager
  ↓
Policy Manager
  ↓
Tool Engine / Kernel
```

## Added

- `zero_cost/action_planner.py`
- `ActionPlan`
- `ActionPlanner`
- default deterministic action rules
- runtime integration through `ACTION_PLAN`
- tests for planner behavior
- tests for runtime integration

## Design boundary

The planner does not execute tools and does not mutate external state.
It only produces an action directive.

To avoid modifying the closed RC1 kernel state schema, the runtime records the generated action plan under:

```python
state.facts["zero_cost_action_plan"]
```

The transition is also visible in the runtime trace as:

```text
ACTION_PLAN
```

## Example

Input intent:

```json
{
  "intent": "concept_franquicia",
  "confidence": 0.5
}
```

Generated action plan:

```json
{
  "action": "knowledge_lookup",
  "source_intent": "concept_franquicia",
  "payload": {
    "tool_key": "franquicia"
  },
  "reason": "zero_cost_rule_plan"
}
```

## Next

Sprint 22 should introduce the Zero-Cost Flow Router.
That component will consume the action plan and choose the internal execution flow while keeping `ACAOSRuntime` as an orchestrator rather than a decision engine.
