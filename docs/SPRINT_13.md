# Sprint 13 - RC1 Test Fixes

## Fixed

- Escalation responses are no longer overwritten by Kernel generation.
- Tool concept lookup works even when a runtime has a registered knowledge tool but minimal domain context.
- Text normalization now repairs common mojibake before removing accents.

## Architectural meaning

This sprint hardens the validation gate instead of adding new features.

The runtime now respects policy escalation as an OS-level stop condition.