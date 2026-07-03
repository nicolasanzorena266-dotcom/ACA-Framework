# ADR-0014 - SDK and CLI Are Developer Experience Boundaries

## Decision

ACA exposes a small SDK factory and CLI.

## Reason

Framework users need a stable way to run ACA without manually wiring Kernel, OS, Domain Pack and Tool Engine.

## Consequences

- Runtime internals remain explicit.
- Developer usage becomes simple.
- CLI can serve as early smoke-test and demo surface.