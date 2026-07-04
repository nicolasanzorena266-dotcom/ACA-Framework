# Sprint 29 - ACA Studio MVP

Sprint 29 introduces the first read-only ACA Studio view model.

## Scope

- `aca_os.studio` with transport-neutral Studio panels.
- Runtime exports through `runtime.studio_view()` and `runtime.export_studio()`.
- SDK support with `process_message(..., include_studio=True)`.
- CLI support through `aca studio`.
- HTML export for lightweight local inspection.

## Architecture

ACA Studio MVP consumes the Runtime Introspection API instead of reading runtime internals directly. This keeps Studio, CLI, REST and future interfaces aligned around a single introspection contract.
