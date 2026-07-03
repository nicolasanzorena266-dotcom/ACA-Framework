# Sprint 15 - Final RC1 Fixture Fix

## Fixed

- The last failing text-normalization test now builds Unicode fixtures from raw UTF-8 bytes.
- This avoids PowerShell rewriting test literals while still validating mojibake repair.

## Result expected

`python -m pytest` should pass the full suite.