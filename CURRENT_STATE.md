# ACA Framework — Current State

**Last updated:** 2026-07-15  
**Status:** Active development  
**Source of truth priority:** running code → tests/benchmarks → architecture documents → this handoff

## Current position

ACA has a stable deterministic Runtime, a growing cognitive/conversational layer, complete turn-level observability, and an external web demo. The project is now transitioning from architecture-first development toward controlled real-world conversational testing.

## Latest completed work

### ACA-303 — Observability Completeness

- Component Registry expanded from 17 to 36 official components.
- SemanticAuthority, SemanticProjector, authority selectors, RuntimeExecutor, LegacyRuntimeExecutor, eight step handlers, Kernel, Compiler, MissionManager, NarrativeResponseComposer and LLMVerbalizer are now observable.
- ConversationalGoal authority metadata was corrected to match runtime behavior.
- Runtime introspection now exposes `output_decision`, including Composer, Conversational-First and LLM verbalization decisions.
- Registry, Authority Dependency Graph and Runtime Introspection were verified against the same official system.
- Verification result: **730/730 tests passed**.
- Existing benchmarks and visible smoke responses remained unchanged.

### Real-world conversational finding

The following conversation was reproduced against the real Runtime:

```text
Usuario: Hola
ACA: Hola. Contame qué necesitás y te oriento.

Usuario: ¿Cómo estás?
ACA: ¿Qué punto querés resolver primero: el arreglo, la denuncia, la documentación o los tiempos?

Usuario: Mis vacaciones
ACA: [repite la misma pregunta]

Usuario: Ninguno
ACA: [repite la misma pregunta]

Usuario: ¿Dios existe?
ACA: [repite la misma pregunta]
```

The investigation found:

- `MissionManager.before_kernel()` creates the mission once and does not reevaluate whether it remains relevant.
- No official component currently owns authority to organically change, finish or abandon an active mission.
- ACA already computes topic-shift-related signals (`TOPIC_SHIFT`, `mission_reevaluation`, `abandonment_criteria`), but none is connected to mission authority.
- Natural topic-shift detection is currently too lexical and narrow.
- The legacy pending-answer classification incorrectly absorbs unrelated user messages when a pending question exists.
- The insurance-specific `user_need` reformulation amplifies the error but is not the root cause.

## Current architectural conclusion

The immediate problem is not simply “topic shift detection.”

> ACA lacks an explicit, governed Mission Lifecycle Authority capable of reevaluating, suspending, replacing, completing or abandoning a mission from conversational evidence.

This is primarily an architecture-and-authority gap, with contributing semantic classification problems.

## Open roadmap items

### Required before controlled real-world testing

1. Establish a reproducible Git baseline for the current working tree.
2. Formalize the freeze list: components and architectural areas that must not be modified during real-world testing without a new ADR.
3. Add the reproduced topic-shift conversation to the permanent conversational benchmark corpus as a regression fixture.
4. Decide the authority model for mission lifecycle changes before implementing a fix.

## Next recommended sprint

**Mission Lifecycle Authority — Architecture Decision**

The sprint should determine:

- who may reevaluate an active mission;
- what evidence can trigger reevaluation;
- whether changes are proposed, gated and atomically selected;
- how rollback works;
- how mission completion, suspension, replacement and abandonment differ;
- how this integrates with existing Semantic Authority discipline without creating a second planner or duplicate writer.

No implementation should begin until this authority decision is explicit.

## Known constraints / do not reopen casually

- Do not add another independent Planner.
- Do not restructure `ConversationState` as part of the mission-lifecycle fix.
- Do not broadly promote Semantic Authority based only on the official benchmark; adversarial performance remains materially weaker.
- Do not promote Candidate Work / Operational Governance / Operational Audit Ledger from Shadow without their own evidence and authority decision.
- Do not treat LLM verbalization as cognitive authority.
- Do not mix provisional and authoritative writes of the same artifact.

## Important documents

Read these before changing direction:

1. `CURRENT_STATE.md`
2. `HANDOFF.md`
3. `docs/architecture/ACA-200_Core_Readiness_Audit.md`
4. `docs/architecture/ACA-300_Conversational_First_Architecture.md`
5. `docs/architecture/ACA-301_Operational_Work_Model_Second_Reassessment.md`
6. `docs/architecture/ACA-302_Real_World_Testing_Roadmap.md`
7. `docs/architecture/ACA-303_Observability_Completeness.md`
8. ACA-019 / ACA-024 for prior authority and forensic findings

## Update rule

This file must be updated at the end of every meaningful sprint or architecture investigation.

A sprint is not considered closed until this file reflects:

- what changed;
- what evidence supports it;
- what decisions were made;
- what remains open;
- the next recommended step.

If this document conflicts with code or tests, code and tests win and the discrepancy must be reported and corrected here.

