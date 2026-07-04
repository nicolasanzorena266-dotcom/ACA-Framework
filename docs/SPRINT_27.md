# Sprint 27 — Execution Trace

## Objective

Introduce a deterministic execution trace as the canonical detailed record for a runtime execution.

## Scope

- Added `ExecutionTrace` and `TraceEvent`.
- Added bounded trace sanitization for JSON-safe exports.
- Runtime now stores the last trace and keeps traces addressable by `trace_id`.
- Output now exposes `execution_trace` without removing the existing state timeline or runtime timeline views.
- CLI now supports `aca trace last --message "..."` for trace inspection.

## Design rule

The trace is passive observability. It must not change runtime decisions, policy behavior, memory writes, action planning, flow routing, or execution planning.

## Validation

The sprint is accepted when the complete local test suite passes.
