# ADR-0007 â€” Domain Packs Are Structured Context

## Decision

Domain Packs are loaded as structured context.

## Reason

The Kernel must not know Galicia, insurance, claims or any domain-specific process.

## Consequences

- Domains can evolve independently.
- The runtime can inject domain context into ContextBundle.
- Domain concepts become testable assets.