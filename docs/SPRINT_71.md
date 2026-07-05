# Sprint 71 — Public Studio Runtime Interaction QA

## Goal

Make the hosted Studio feel like a usable runtime interaction surface instead of a technical demo shell.

## Scope

- The phone simulation now has an explicit **Enviar** action and supports Enter.
- The conversation scrolls inside the phone panel instead of expanding the full Studio page.
- **Reiniciar** clears the visible conversation and resets the public reading state.
- Public-facing labels are Spanish and human-readable.
- Diagnostic phrases about code exposure and internal decisions were removed from the main view.
- Runtime demo responses were humanized so users get an actionable answer rather than raw domain/intent/flow strings.

## Architectural boundary

ACA Studio remains a surface over the runtime. The interface does not own business logic and does not turn the project into a regular chatbot wrapper. The runtime still selects the route; the Studio only presents the interaction.

## Validation

Targeted validation covers the Sprint 71 UX requirements plus the Sprint 70 compatibility markers required by older tests.
