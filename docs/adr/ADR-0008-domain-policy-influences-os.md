# ADR-0008 - Domain Policy Influences ACA OS

## Decision

Domain context may influence ACA OS policy decisions.

## Reason

A domain-specific agent must obey domain limits without modifying Kernel behavior.

## Consequences

- Domain Packs can guide policy decisions.
- The Kernel remains unchanged.
- Policy results become explicit CSM state.
- Escalations become explainable.