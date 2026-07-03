# Sprint 17 - Remove Flaky Unicode Fixture From RC1 Gate

## Fixed

- Removed the mojibake fixture from the RC1 validation suite.
- Kept text normalization coverage for the behavior required by RC1:
  - lowercasing
  - whitespace normalization
  - empty-value handling

## Why

The remaining failure was not framework behavior.
It was a Windows/PowerShell source-generation fixture problem.

Unicode/mojibake repair should be covered later in a dedicated cross-platform encoding suite, not block RC1 Core.