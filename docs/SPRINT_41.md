# Sprint 41 — REST API Foundation

Sprint 41 adds the first stable REST surface for ACA Runtime Interfaces.

The REST layer is intentionally thin:

- no business logic inside HTTP handlers;
- no direct access from transport code to internal components;
- runtime execution delegated through Runtime API / SDK boundaries;
- deterministic JSON responses;
- predictable error envelopes;
- stdlib-only HTTP server for zero-cost/offline operation.

## Added

- `aca_os.runtime_rest.RuntimeRESTAPI`
- `aca_os.runtime_rest.RESTResponse`
- `tools/aca_rest.py`
- REST endpoint catalog via `/health`
- Runtime status, components, plugins, metrics and introspection endpoints
- Runtime execution endpoint
- Execution trace endpoint
- Session replay endpoint
- REST service and HTTP adapter tests

## Endpoints

```text
GET  /health
GET  /runtime/status
GET  /runtime/components
GET  /runtime/plugins?root=examples/plugins
GET  /runtime/metrics
GET  /runtime/introspection
POST /runtime/run
POST /runtime/trace
POST /sessions/replay
```

## Validation

```bash
python -m pytest -q
```
