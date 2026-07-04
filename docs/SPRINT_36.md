# Sprint 36 — Plugin Loader

## Status

Completed.

## Goal

Add the first deterministic Plugin SDK loader layer without executing plugin implementation code.

ACA can now discover plugin manifests from disk, validate them through the Sprint 35 contract and register their capabilities in the Component Registry.

## Delivered

- `PluginLoader` runtime service.
- Deterministic recursive discovery of `plugin.json` manifests.
- Manifest loading through `PluginManifest` and `PluginContract`.
- Component Registry registration for loaded plugins.
- Duplicate plugin detection.
- Non-strict observable failure results.
- Strict mode for hard validation failures.
- Runtime APIs:
  - `load_plugins(path)`
  - `export_plugins()`
- Plugin Loader runtime component registration.
- Full test coverage for discovery, loading, duplicate handling, dependency validation and runtime integration.

## Boundary

Sprint 36 does not import or execute plugin entrypoints.

```text
Plugin Folder
  │
  ▼
plugin.json
  │
  ▼
Plugin Manifest
  │
  ▼
Plugin Contract
  │
  ▼
Plugin Loader
  │
  ▼
Component Registry
```

## Architecture Rule

Plugins become visible to ACA only through Runtime Services.
They do not depend on runtime internals and the loader does not depend on plugin implementation code.
