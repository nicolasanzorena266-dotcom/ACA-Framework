# Sprint 2 â€” Tool Engine + Context Manager

## Added

- `aca_os/tool_engine.py`
- `aca_os/context_manager.py`
- `tests/test_tool_context.py`
- `docs/adr/ADR-0005-tool-engine-context-manager.md`

## Architectural meaning

ACA can now represent external tools as evidence providers and construct explicit context bundles.

This is the first real step toward runtime orchestration beyond the Kernel.
