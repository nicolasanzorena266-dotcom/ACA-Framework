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
