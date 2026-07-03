# Sprint 6 - Text Normalization Foundation

## Added

- `aca_os/text.py`
- Unicode-safe `normalize_text`
- PolicyManager now uses shared normalization
- Policy tests for accented Spanish inputs

## Why this matters

ACA must work with real Spanish text without relying on fragile hardcoded accent maps.

This sprint removes a Windows encoding weakness and turns normalization into a reusable OS utility.