# Sprint 32 — Metrics Engine

## Status

Completed.

## Scope

Sprint 32 introduces the Metrics Engine as an external runtime capability for deterministic observability.

Execution Trace remains the source of truth. Metrics Engine only aggregates trace data into a stable read API.

## Delivered

- Counter metrics
- Gauge metrics
- Histogram metrics
- Percentiles: p50, p95, p99
- Component-level metrics
- Runtime-level metrics
- Manual counter/gauge API for future runtime services
- Runtime metrics export API
- Introspection integration
- Tests for standalone and runtime-integrated metrics

## Architecture rule

Interfaces consume metrics through Runtime API only.

```text
Interface
    │
Runtime API
    │
Metrics Engine
    │
Execution Trace
```

No UI, CLI, REST or MCP layer should compute metrics directly.
