# ADR-0015 - RC1 Validation Gate

## Decision

RC1 Core requires an explicit validation gate.

## Reason

The project moved from architecture design into executable framework behavior.

## Consequences

- New feature work should pause until the RC1 validation suite passes.
- Smoke tests become the minimum acceptance layer.
- RC1 closure is based on behavior, not document count.