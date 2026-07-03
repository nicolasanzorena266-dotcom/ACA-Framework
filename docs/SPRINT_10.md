# Sprint 10 - Output Event + Trace

## Added

- `ACAOutput`
- `ACAOutput.from_state`
- `ACAOSRuntime.process_output`
- `explain_state`
- Output tests

## Architectural meaning

ACA now has a product-facing output boundary.

Integrations do not need to consume the full CSM directly.
They can consume ACAOutput while the full CognitiveState remains available for debugging and Studio.