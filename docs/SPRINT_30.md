# Sprint 30 — Session Persistence & Replay

Sprint 30 introduces the first durable execution boundary for ACA Runtime.

## Added

- `ExecutionSession` as a serializable execution capsule.
- Session save/load helpers.
- Runtime replay from a saved session.
- Session comparison for deterministic behavior checks.
- CLI session commands:
  - `aca session save`
  - `aca session show`
  - `aca session replay`
  - `aca session compare`
- Tests covering runtime persistence, replay and CLI workflows.

## Architecture

A session stores the original input event, final state, output, trace and
introspection snapshot. This keeps ACA Studio, CLI and future API clients away
from private runtime internals while enabling replay/debugging workflows.
