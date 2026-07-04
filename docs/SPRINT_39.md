# Sprint 39 — Example Plugins

## Status

Completed.

## Goal

Provide repository-hosted Plugin SDK examples that can be discovered, validated,
loaded and lifecycle-managed without importing plugin entrypoints.

## Added

- `examples/plugins/echo_tool`
- `examples/plugins/context_snapshot`
- `examples/plugins/decision_audit`
- `aca_os.plugin_examples` catalog and validation helpers
- Deterministic example plugin tests

## Architecture Notes

Example plugins remain metadata-first. Their `plugin.py` files define future
entrypoint targets, but Sprint 39 keeps the loader contract unchanged: no plugin
code is imported or executed during discovery, validation, load or lifecycle
operations.

This gives the Plugin SDK real fixtures for future CLI, REST, MCP and Studio
demos without weakening the Runtime boundary.
