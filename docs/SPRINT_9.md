# Sprint 9 - Memory Persistence

## Added

- `MemoryStore`
- `JsonMemoryStore`
- Memory serialization
- Memory loading
- Automatic persistence on memory updates
- Memory persistence tests

## Architectural meaning

ACA memory is no longer only in-process.

The reference runtime can persist cognitive continuity without requiring a database.