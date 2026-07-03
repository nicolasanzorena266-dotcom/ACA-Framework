# ADR-0020 - Unicode Edge Tests Moved Out of RC1 Gate

## Decision

Unicode/mojibake edge-case tests are not part of the RC1 Core validation gate.

## Reason

The framework behavior required for RC1 is stable, but generated PowerShell fixtures are corrupting Unicode test data.

## Consequences

- RC1 validates actual framework behavior.
- Unicode edge testing moves to a dedicated cross-platform suite.
- RC1 is not blocked by terminal/source-generation artifacts.