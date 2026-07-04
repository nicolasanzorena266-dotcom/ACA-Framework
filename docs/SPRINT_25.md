# Sprint 25 — Runtime Observability / Internal Event Bus

Sprint 25 introduces a passive in-process Event Bus for runtime observability.

## Scope

- Add `RuntimeEvent` as a serializable internal event envelope.
- Add `EventBus` as a zero-cost, in-memory publisher/subscriber component.
- Wire `ACAOSRuntime` to emit decision events without altering the execution path.
- Expose observability components in `aca inspect runtime`.

## Runtime events

The runtime now emits observable events for:

- process start
- intent match
- action plan
- flow route
- execution plan creation
- policy evaluation
- process completion

## Design rule

The Event Bus is passive. It records and publishes runtime decisions, but it does not decide, mutate state, call tools, or invoke LLMs.

This prepares the next layer for Runtime Timeline, Execution Trace, ACA Studio MVP, and visual decision inspection.
