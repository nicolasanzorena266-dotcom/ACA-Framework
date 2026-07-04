# Sprint 26 — Runtime Timeline

## Objective

Introduce a normalized runtime timeline that can be consumed by future inspectors, execution traces, and ACA Studio without changing runtime decisions.

## Added

- `RuntimeTimelineEntry`
- `RuntimeTimeline`
- `ACAOutput.runtime_timeline`
- DX runtime inspection exposure for `runtime_timeline`

## Design rule

The timeline is read-only and observational. It must not influence planning, routing, policy, tool execution, memory, or output generation.

## Acceptance

- Existing `trace` remains compatible.
- Runtime events remain available through the Event Bus.
- Output now includes a normalized `runtime_timeline` envelope.
- Full test suite remains green.
