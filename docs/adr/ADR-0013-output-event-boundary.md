# ADR-0013 - Output Event Boundary

## Decision

ACA exposes a product-facing `ACAOutput` separate from the full CSM.

## Reason

The CSM is an internal cognitive state.
Applications need a stable output contract.

## Consequences

- Integrations can consume simple structured output.
- Studio can still inspect the full CSM.
- Runtime can support both low-level and product-facing APIs.