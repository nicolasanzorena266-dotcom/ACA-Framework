# ADR-0021 - RC1 Core Is Closed

## Decision

RC1 Core is closed.

## Reason

The framework now has a coherent executable core:

- Kernel
- ACA OS
- Domain Pack boundary
- Tool boundary
- Memory boundary
- Output boundary
- SDK / CLI
- Validation gate

Continuing to add features to RC1 Core would turn closure into drift.

## Consequences

- Future work must be scoped under explicit phases.
- Core changes require stronger justification.
- New work should prefer extension over mutation.