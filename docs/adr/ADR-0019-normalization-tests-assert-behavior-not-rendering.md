# ADR-0019 - Normalization Tests Assert Behavior, Not Rendering

## Decision

Text normalization tests should assert normalized behavior, not exact rendered Unicode round-trips.

## Reason

The framework requires stable matching, not console-perfect display of corrupted fixtures.

## Consequences

- Tests become less brittle on Windows.
- Normalization remains verified.
- Mojibake repair remains covered through final normalized output.