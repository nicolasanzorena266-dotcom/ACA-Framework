# Sprint 7 - Conversation Manager

## Added

- `aca_os/conversation_manager.py`
- Conversation sessions
- Conversation turns
- Runtime integration
- Conversation lifecycle tests

## Architectural meaning

ACA now tracks conversation continuity as an ACA OS concern.

The Kernel still only executes operation graphs.
The Conversation Manager owns session lifecycle and active CSM continuity.