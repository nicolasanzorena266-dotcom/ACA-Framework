# Sprint 47 — Domain Pack Validator

## Goal

Add a deterministic validation boundary for Domain Packs before they can be loaded or registered.

## Scope

- Added `DomainPackValidator` as an external Domain Pack governance capability.
- Added structured validation issues, results and snapshots.
- Validates manifest parse errors, runtime compatibility, dependency declarations, asset existence, supported formats and JSON asset readability.
- Integrated `DomainPackLoader` with the validator before component registration.
- Registered `domain_pack_validator` as a runtime-owned observable component.
- Added runtime export for Domain Pack validation state.

## Constraints preserved

- No Domain Pack code is imported.
- No direct dependency from packs to runtime internals.
- Loader remains manifest-first and registry-bound.
- RC1 Core remains untouched.

## Validation

```bash
python -m pytest -q
```
