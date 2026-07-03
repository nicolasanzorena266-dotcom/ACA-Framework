# Sprint 14 - Final RC1 Test Fix

## Fixed

- Text normalization tests now build accented Spanish strings through Unicode escapes.
- This avoids PowerShell/source-file encoding corruption in the test itself.

## Architectural meaning

The framework logic was valid.
The remaining failure was a test fixture encoding issue.