# Sprint 63 — Deployment Smoke Tests

Sprint 63 adds platform-neutral smoke tests for ACA hosted demos.

The smoke layer verifies the public demo path through REST adapter routes before a real hosting attempt:

- platform health
- runtime status
- Studio bootstrap and binding
- hosting target validation
- hosted runtime healthcheck validation
- hosted Studio asset validation
- deterministic Domain Pack demo flow

The smoke tests are intentionally in-process. They do not call external hosts, do not require a socket server, and do not move business logic into deployment code.

## Added

- `aca_os/deployment_smoke_tests.py`
- `/deploy/smoke-tests`
- `/deploy/smoke-tests/run`
- `/deploy/smoke-tests/validate`
- `deploy/deployment-smoke-tests.json`
- deployment smoke coverage in hosting contract and hosted healthcheck

## Validation

Run:

```powershell
python -m pytest -q
```
