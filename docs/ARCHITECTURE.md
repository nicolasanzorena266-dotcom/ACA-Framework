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


## Metrics Engine

Metrics Engine is a passive runtime service. It derives counters, gauges, histograms and component metrics from Execution Trace. Execution Trace remains the source of truth; Timeline remains a simplified view. Interfaces must consume metrics through the Runtime API and must not calculate observability state themselves.
