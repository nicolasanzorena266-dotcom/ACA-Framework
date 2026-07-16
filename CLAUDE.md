# CLAUDE.md — ACA Framework Working Contract

## Mandatory startup

At the beginning of every session:

1. Read `CURRENT_STATE.md`.
2. Read `HANDOFF.md`.
3. Inspect `git status`.
4. Read only the architecture documents relevant to the current problem.
5. Verify repository reality before trusting summaries.

## Authority and scope

Act as an implementation engineer and technical auditor inside the architecture already adopted by ACA.

Do not:

- invent a new Planner;
- create parallel authorities;
- widen scope silently;
- restructure `ConversationState` incidentally;
- promote Shadow components without explicit evidence and an authority decision;
- use the LLM as cognitive or operational authority;
- commit, push, reset, checkout or delete unrelated work unless explicitly instructed.

## Completion rule

A meaningful sprint is not complete until:

- required tests pass;
- relevant benchmarks pass;
- visible behavior changes are documented;
- architectural consequences are documented;
- `CURRENT_STATE.md` is updated.

If `CURRENT_STATE.md` is stale, update it before presenting final completion.

## Session continuity

The repository, not the chat session, owns project memory.

When prior chat context conflicts with repository evidence, report the conflict and follow the repository evidence.

