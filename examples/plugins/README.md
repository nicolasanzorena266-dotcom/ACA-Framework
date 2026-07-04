# ACA Plugin SDK Examples

Sprint 39 adds manifest-first example plugins. They are intentionally small and safe:

- `echo_tool`: deterministic tool capability example.
- `context_snapshot`: read-only runtime context capability example.
- `decision_audit`: observability-only decision graph audit example.

These examples are valid Plugin SDK contracts. The current loader discovers, validates,
registers and lifecycle-manages their metadata without importing or executing entrypoints.
