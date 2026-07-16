# ACA Framework — Session Handoff

This document is the entry point for a new Claude Code, Codex, Gemini or human engineering session.

## Startup protocol

Before proposing or modifying anything:

1. Read `CURRENT_STATE.md`.
2. Run `git status`.
3. Read the latest relevant architecture documents named in `CURRENT_STATE.md`.
4. Confirm the current test baseline and whether the working tree contains uncommitted work.
5. Compare `CURRENT_STATE.md` with code and tests.
6. Report contradictions before proceeding.

Do not reconstruct the project from chat history unless repository evidence is incomplete.

## Working rules

- Treat running code and tests as the primary source of truth.
- Distinguish facts, hypotheses, decisions and consequences.
- Do not reopen settled decisions without new evidence.
- Prefer narrow, reversible changes.
- Never create a second authority for an artifact that already has one.
- Use Shadow → benchmark → gated selector → rollback for authority migrations.
- Do not claim a component is active because documentation says so; verify live callers.
- Do not commit or push unless explicitly requested.
- Run relevant tests and benchmarks before closing implementation work.
- Update `CURRENT_STATE.md` before declaring a sprint complete.

## Current next step

Read `CURRENT_STATE.md`. The current recommended work is an architecture decision for Mission Lifecycle Authority, not immediate implementation.

## Closing protocol

Before ending a meaningful session, update `CURRENT_STATE.md` with:

- sprint or investigation completed;
- files changed;
- test and benchmark evidence;
- architectural decisions;
- rejected alternatives;
- unresolved risks;
- exact recommended next step.

If the session ends unexpectedly, create a brief `SESSION_RECOVERY.md` containing whatever remains incomplete.

