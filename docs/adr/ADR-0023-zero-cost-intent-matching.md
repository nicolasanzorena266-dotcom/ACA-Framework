# ADR-0023 - Zero-Cost Intent Matching

## Decision

ACA introduces a zero-cost rule-based Intent Matcher.

## Reason

ACA should function without LLM dependency.

## Consequences

- Basic intent classification works locally.
- Intent decisions are inspectable.
- More advanced NLU can be added later without replacing the core.