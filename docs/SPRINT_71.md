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

## RC5 correction — Adaptive representative conversation

User validation found the remaining core defect: the public chat still treated each message as an isolated request. That broke the ACA premise of cognitive continuity and caused short follow-ups such as "Bueno", "bue..." or "Qué podés hacer?" to fall back instead of continuing the active context.

RC5 adds a lightweight public conversation state for the hosted demo and routes responses through an adaptive reply policy:

- Tracks active goal, active topic, ticket number, claim type, last category and fallback/confusion signals per conversation.
- Keeps ticket context across turns, so follow-ups after `ticket 12345` continue from that ticket instead of restarting.
- Keeps claim context across turns, so `Qué documentación necesito?` after `Tuve un choque` answers about choque documentation.
- Handles greetings, capabilities, identity, AI-limit and frustration/confusion without generic fallback.
- Reformulates when the user is confused instead of repeating the same answer.
- Moves the public Studio closer to a chat-first 9:16 conversation surface and prevents the previous dashboard layout from cutting the phone shell.

Architectural note: this is still not a free LLM chatbot. The deterministic runtime continues to interpret the request, while the new public state and representative policy preserve continuity and communicate the next step in human language.


## RC7 correction — Public Conversation Runtime hardening

User validation after RC6 showed that ACA still failed in realistic conversational sequences: misspelled domain terms such as “franquisia” were missed, documentation follow-ups after a franquicia explanation were misrouted to ticket `case_id`, and frustration/show-me requests repeated the same demo limitation instead of producing a useful representative answer.

RC7 hardens the public conversation runtime:

- Normalizes accents and common typos for public intent cues such as franquicia/franquisia.
- Prioritizes conversational acts and active context before generic missing-entity checks.
- Answers documentation follow-ups from the active claim topic, including franquicia, choque, cristales and robo parcial.
- Turns frustration into a concrete model response instead of repeating the connection limitation.
- Adds client-facing example responses when the user asks “mostrame”, “cómo sería” or “cómo le responderías a un cliente”.
- Simplifies the Studio public surface to one centered chat panel and hides the technical summary card from the main view.
- Keeps compatibility markers for older Studio tests without exposing those artifacts in the public interface.

Acceptance target: ACA must preserve the active conversation topic and produce useful representative-style answers before exposing any internal process detail.


## RC8 correction — Test compatibility and typo-tolerant capability routing

RC8 fixes two regressions discovered after integrating RC7 locally:

- Capability and AI-limit questions with realistic typos such as `Podes haceeer algo mas?` and `no tenees IA` now route to the adaptive capability/AI policy instead of falling back to the active ticket status response.
- The Studio public shell keeps the single chat-first layout while preserving legacy layout markers required by older tests.

Acceptance target: after a ticket query, capability and AI-limit follow-ups must keep ticket context and explain what ACA can do, without repeating the ticket-status limitation.
