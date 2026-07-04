# Changelog


## Sprint 34 — Studio Evolution

- Evolved ACA Studio from MVP panels into a Runtime Intelligence view model.
- Added Runtime Health, Decision Graph and Component Registry Studio panels.
- Added `build_studio_intelligence()` as a read-only projection over Runtime Introspection.
- Exposed decision graph, action plan, execution flow and execution plan summaries through introspection state summaries.
- Updated Studio HTML export for richer Runtime Intelligence rendering.
- Added Studio Evolution tests and kept the existing Studio export contract compatible.


## Sprint 31 — Decision Graph Engine

- Added deterministic Decision Graph Engine.
- Persisted `zero_cost_decision_graph` in runtime facts.
- Added `DECISION_GRAPH` operation to execution trace.
- Added `runtime.decision_graph_created` event bus event.
- Updated runtime introspection and DX inventory.
- Added Sprint 31 documentation.
- Full suite: 89 passing tests.

## RC1 Core Closed

- Added ACA Kernel reference implementation.
- Added ACA OS runtime orchestration.
- Added Conversation Manager.
- Added Mission Manager.
- Added Policy Manager.
- Added Tool Engine.
- Added Context Manager.
- Added Memory Engine.
- Added JSON Memory Store.
- Added ACAOutput boundary.
- Added Galicia Domain Pack v1.
- Added SDK factory.
- Added CLI.
- Added smoke validation.
- Added RC1 validation and closure docs.

## RC1 Core Bootstrap

- Created official repository structure.
- Consolidated Kernel / ACA OS / Domain Pack separation.
- Added core specification.
- Added ADR and RFC structure.
- Added reference Kernel skeleton.
- Added Mission, Policy and Memory OS contracts.

## Sprint 33 — Component Registry

- Added typed Component Registry service.
- Added component descriptors with metadata, capabilities, dependencies and lifecycle state.
- Added runtime component auto-registration.
- Added `ACAOSRuntime.export_components()`.
- Updated introspection to consume Component Registry snapshots.
- Added registry lifecycle and runtime integration tests.

## Sprint 32 — Metrics Engine

- Added deterministic Metrics Engine.
- Added runtime metrics export API.
- Added counters, gauges, histograms and percentile aggregation.
- Added component-level metrics derived from Execution Trace.
- Integrated metrics into runtime introspection.
- Added Sprint 32 documentation.
