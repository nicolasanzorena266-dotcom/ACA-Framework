# Sprint 6 - Text Normalization Foundation

## Added

- `aca_os/text.py`
- Unicode-safe `normalize_text`
- PolicyManager now uses shared normalization
- Policy tests for accented Spanish inputs

## Why this matters

ACA must work with real Spanish text without relying on fragile hardcoded accent maps.

This sprint removes a Windows encoding weakness and turns normalization into a reusable OS utility.

## Superseded by Text Normalization Boundary

The reusable API now lives in `aca_core.text`. `aca_os/text.py` was removed so
normalization is a framework-level boundary shared by OS, Kernel, plugins and
public conversation layers.
