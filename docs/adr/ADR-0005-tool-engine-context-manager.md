# ADR-0005 â€” Tool Engine and Context Manager

## Decision

ACA OS owns the Tool Engine and Context Manager.

## Reason

The Kernel must remain domain-agnostic and tool-agnostic.

Tools produce structured evidence.
The Context Manager selects the minimum relevant context for downstream operations.

## Consequences

- Tools never generate final user responses.
- Context is explicit and inspectable.
- The Kernel remains independent from APIs, CRMs, search services and LLM providers.
