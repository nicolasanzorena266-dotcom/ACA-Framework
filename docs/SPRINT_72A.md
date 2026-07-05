# Sprint 72A — ACA Platform Plugin Architecture

Sprint 72A starts the platform turn: domains are no longer Core concerns. The new architecture introduces a business-agnostic Core, a base Plugin SDK, versioned plugin manifests, capability routing, plugin-local state, trace compatibility and eval hooks.

## Delivered

- Added `aca_core` with the platform plugin runtime primitives.
- Added `aca_plugin_sdk` as the public SDK surface for plugin authors.
- Added versioned manifest parsing and validation.
- Added `PluginLoader`, `PluginRegistry` and `CapabilityRegistry`.
- Added capability-based routing with generic fallback.
- Added `DomainPlugin` contract.
- Added separate `CorePolicy` and `DomainPolicy` layers.
- Added isolated state by conversation, plugin and capability.
- Added plugin-aware trace recorder.
- Added eval hook registry.
- Added `plugins/generic.open_chat` as the fallback plugin.
- Added `plugins/galicia.insurance` as a domain plugin.
- Added removal, mock-plugin and anti-contamination tests.
- Added ADR-0007 — Business-Agnostic Core Principle.

## Validation

Targeted Sprint 72A suite:

```bash
pytest -q tests/test_platform_plugin_architecture.py
```

Expected result: 5 passed.

## Deferred to Sprint 72B

The public conversation product layer remains intentionally untouched: no new UI, no layout work, no copy patching and no RC11 product surface changes.
