# ADR-0018 - Byte Fixtures for Cross-Platform Unicode Tests

## Decision

Unicode-sensitive tests may build fixtures from byte sequences.

## Reason

PowerShell-generated files can corrupt literal Unicode and even escaped Unicode depending on the generation path.

## Consequences

- Unicode tests become stable across Windows shells.
- Runtime code remains unchanged.
- Fixture corruption is isolated from framework behavior.