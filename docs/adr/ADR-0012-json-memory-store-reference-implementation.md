# ADR-0012 - JSON Memory Store Reference Implementation

## Decision

The first ACA memory persistence implementation uses JSON files.

## Reason

JSON keeps the reference runtime simple, inspectable and portable.

## Consequences

- No database dependency for RC1.
- Memory can be inspected manually.
- Future stores can implement the same `MemoryStore` boundary.