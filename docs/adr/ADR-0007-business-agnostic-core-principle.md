# ADR-0007 — Business-Agnostic Core Principle

## Status
Accepted — Sprint 72A.

## Context
ACA is moving from an application-shaped runtime to a platform-shaped runtime. The Core must provide cognition, routing, policy boundaries, state, trace and eval hooks without knowing any brand, client, workflow or operational domain.

Earlier domain packs proved useful as structured context, but they still allowed domain assumptions to sit too close to runtime behavior. Sprint 72A establishes the stricter boundary: the Core owns the protocol; plugins own the business.

## Decision
ACA Core is business-agnostic.

Rules:

1. The Core never imports specialized plugins.
2. The Core never contains business vocabulary.
3. The Router selects capabilities, not brands.
4. Plugins declare capabilities through a versioned manifest.
5. Plugin state is isolated by conversation, plugin and capability.
6. Core policy and domain policy are separate layers.
7. Trace records active plugin and capability without requiring Core knowledge of the domain.
8. Eval hooks are registered by plugin and executed through a generic contract.
9. Removing a specialized plugin must not break Core boot, routing or fallback behavior.
10. Adding a new plugin must not require Core edits.

## Consequences
A domain becomes installable infrastructure, not runtime code. A plugin may contain knowledge, prompts, tools, policy, evals and assets, but the Core only sees its manifest and exported capabilities.

This makes ACA Platform extensible across domains while preserving a stable cognitive runtime.
