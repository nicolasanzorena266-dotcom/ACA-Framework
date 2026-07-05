# Sprint 60 — Hosting Target Contract

## Goal

Define a platform-neutral hosting target contract for the public ACA Studio demo.

This sprint does not deploy ACA. It defines what a hosted platform must provide and what ACA exposes when running as a public web demo.

## Added

- `aca_os/hosting_target_contract.py`
- `/hosting/target` Runtime/REST endpoint
- `/hosting/target/validate` Runtime/REST endpoint
- `deploy/hosting-target-contract.json`
- tests for contract creation, validation and REST exposure

## Contract boundaries

The hosting contract describes:

- startup command
- host and port strategy
- healthcheck
- required public routes
- required files
- environment variables
- compatible generic hosting targets
- acceptance criteria

It does not own Runtime behavior, domain behavior, intent matching, flow execution or business logic.

## Validation

Targeted validation used while building this sprint:

```bash
python -m pytest tests/test_hosting_target_contract.py -q
```
