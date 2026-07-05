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


## RC3 correction — Conversation quality and cellphone shell

User validation found that the Studio still looked like a basic dashboard and the chat still behaved like a deterministic fallback screen. RC3 tightens the public interaction layer:

- The phone frame now uses real cellphone proportions and keeps conversation scrolling inside the device.
- ACA answers identity and AI-capability questions directly instead of repeating the generic fallback.
- The visible process detail is rewritten as a human explanation instead of a technical trace dump.
- The interface hides `<max-depth>` artifacts from module labels.
- The public action is renamed to **Probar ejemplo** while keeping hidden compatibility markers required by older tests.

This does not turn ACA into a ChatGPT clone. It makes the current public runtime honest about its limits while still behaving like an interaction surface, not a broken classifier.


## RC4 correction — Representative experience alignment

User validation showed that the UI still had too much dashboard weight and that ACA was speaking about its own runtime instead of answering like a service representative. RC4 changes the public experience around the original ACA principle: understand first, communicate clearly, and never invent system data.

- Removed the visible Runtime / Components / Modules / Events metric cards from the main Studio surface.
- Enlarged the phone shell to a 9:16 story-style conversation panel and removed the fake clock.
- Added `RepresentativeAnswerComposer` as the public language layer over deterministic routing.
- Rewrote ticket-status answers so ACA explains the demo limitation naturally and shows what it would prepare: status, responsible and next step.
- Added natural answers for identity, AI-capability, confusion and basic Galicia-style siniestro scenarios such as choque, cristales, robo parcial and franquicia.
- Kept runtime interpretation and trace detail behind **Ver proceso** instead of leaking it into the chat response.

Acceptance target: ACA should feel like a constrained representative simulation, not a classifier dashboard with a chat box.
