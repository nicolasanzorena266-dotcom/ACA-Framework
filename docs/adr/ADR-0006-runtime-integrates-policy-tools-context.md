# ADR-0006 â€” Runtime Integrates Policy, Tools and Context

## Decision

ACA OS Runtime coordinates Policy Manager, Tool Engine and Context Manager around Kernel execution.

## Reason

The Kernel must remain pure and tool-agnostic.
The OS layer is responsible for deciding whether tools are required and for building the context bundle.

## Consequences

- Tool evidence becomes explicit CSM state.
- Context Bundle becomes inspectable.
- The runtime flow is now closer to ACA's target architecture.
