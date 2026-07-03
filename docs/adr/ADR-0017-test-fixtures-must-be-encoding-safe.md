# ADR-0017 - Test Fixtures Must Be Encoding Safe

## Decision

Tests that require accented or special Unicode characters should use Unicode escapes when scripts are generated through Windows PowerShell.

## Reason

PowerShell and terminal encoding can corrupt literal accented characters when generating source files.

## Consequences

- Tests remain stable across Windows and Linux.
- Runtime normalization remains unchanged.
- Source-generation scripts avoid accidental mojibake.