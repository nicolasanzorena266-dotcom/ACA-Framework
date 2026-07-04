# Sprint 51 — Studio Runtime Binding

Sprint 51 binds ACA Studio more explicitly to the local Runtime API without moving business logic into the browser or HTTP adapter.

## Added

- `aca_os/studio_runtime_binding.py`
- `/studio/binding` Runtime/REST endpoint
- `/studio/binding/run` Runtime/REST endpoint
- Studio HTML panels for Runtime binding, Domain context, Metrics and last execution trace summary
- Tests for Runtime API, REST API and local web server binding behavior

## Boundary

Studio remains an interface. It only consumes Runtime API payloads.

Domain logic stays in Domain Packs and Runtime services.
