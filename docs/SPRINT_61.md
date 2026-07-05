# Sprint 61 — Hosted Runtime Healthcheck

## Goal

Add a hosted-runtime healthcheck contract for ACA public web demos. The healthcheck gives hosting platforms and smoke tests a single deterministic payload that explains whether the hosted runtime, Studio asset, default Domain Pack, route contract and port configuration are ready.

## Added

- `aca_os/hosted_runtime_healthcheck.py`
- Runtime API endpoints for `/hosting/healthcheck` and `/hosting/healthcheck/validate`
- REST routes for hosted healthcheck and validation
- Hosting target contract routes updated with hosted healthcheck paths
- Deployment JSON regenerated with hosted healthcheck routes
- Tests for healthcheck contract, REST routing and endpoint catalog exposure

## Design constraints

The hosted healthcheck is an adapter-level contract only. It does not move business logic into hosting code, does not require external AI, and does not mutate Runtime Core. Runtime Trace remains the source of truth; this sprint only exposes a deployment-facing readiness view.

## Validation

Targeted validation used for the sprint:

```bash
python -m pytest tests/test_hosted_runtime_healthcheck.py tests/test_hosting_target_contract.py tests/test_runtime_rest.py tests/test_public_demo_runtime_adapter.py tests/test_web_demo_deployment_guide.py -q
```

Expected targeted result:

```text
31 passed
```
