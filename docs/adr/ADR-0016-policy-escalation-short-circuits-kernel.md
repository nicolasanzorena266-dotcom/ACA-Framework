# ADR-0016 - Policy Escalation Short-Circuits Kernel

## Decision

When PolicyManager returns ESCALATE, ACA OS should not continue into normal Kernel response generation.

## Reason

Escalation is a policy-level decision. Letting the Kernel continue may overwrite the escalation response.

## Consequences

- Escalation messages remain stable.
- Policy decisions have real control over runtime flow.
- Kernel stays unchanged.