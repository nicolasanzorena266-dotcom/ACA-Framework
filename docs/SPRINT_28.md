# Sprint 28 — Runtime Introspection API

Sprint 28 introduces a read-only Runtime Introspection API.

## Objective

Expose a stable inspection contract for future interfaces without coupling them to runtime internals.

## Added

- `aca_os/introspection.py`
- `runtime.inspect_runtime()`
- `runtime.export_introspection()`
- SDK `process_message(..., include_introspection=True)`
- CLI `aca inspect session --message "..."`
- CLI `--introspection` flag for message execution

## Contract

The introspection snapshot includes:

- runtime id and status
- component inventory
- last state summary
- last trace summary
- normalized timeline
- event bus state
- runtime metrics

## Architecture note

ACA Studio, REST, MCP and future visual inspectors should consume this API instead of reaching into runtime private fields.
