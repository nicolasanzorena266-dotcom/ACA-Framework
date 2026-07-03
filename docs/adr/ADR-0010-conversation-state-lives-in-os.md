# ADR-0010 - Conversation State Lives in ACA OS

## Decision

Conversation session state belongs to ACA OS.

## Reason

The Kernel should not know whether an event came from WhatsApp, email, web chat or a multi-turn session.

## Consequences

- Conversations become trackable without modifying Kernel.
- The active CSM can be associated with a session.
- Runtime can process multi-turn flows more consistently.