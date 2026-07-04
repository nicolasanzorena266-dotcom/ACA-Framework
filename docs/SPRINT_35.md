# Sprint 35 — Plugin Manifest & Contract

Status: completed.

## Goal

Start Epic 3 by defining the deterministic Plugin SDK boundary.

Sprint 35 does not load or execute plugin code. It defines the manifest and contract layer that future loader, validator and lifecycle stages must consume before touching any implementation.

## Delivered

- `PluginManifest` contract.
- `RuntimeCompatibility` declaration.
- `PluginEntrypoint` declaration.
- `PluginCapability` metadata.
- `PluginPermission` metadata.
- `PluginHook` metadata.
- `PluginContract` projection.
- Conversion from plugin manifest to `ComponentDescriptor`.
- JSON and file parsing helpers.
- Duplicate capability / permission / hook validation.
- Component Registry integration path for future plugins.

## Architecture rule

Plugins are not runtime internals.

```text
Plugin
  │
  ▼
Plugin Manifest
  │
  ▼
Plugin Contract
  │
  ▼
Component Registry
  │
  ▼
Runtime API
```

No plugin may depend directly on runtime components. It must declare capabilities, permissions and compatibility first.

## Validation

Full suite passing with 107 tests.
