# Sprint 38 — Plugin Lifecycle

Status: completed.

Sprint 38 adds the first deterministic lifecycle manager for Plugin SDK plugins.

## Goals

- Keep plugin code execution out of the Runtime Core.
- Add observable lifecycle transitions for loaded plugins.
- Synchronize plugin lifecycle state with Component Registry state.
- Prepare the Plugin SDK for future executable hooks and example plugins.

## Added

- `PluginLifecycleManager`
- `PluginLifecycleState`
- `PluginLifecycleRecord`
- `PluginLifecycleEvent`
- `PluginLifecycleSnapshot`
- Runtime APIs:
  - `load_plugins()` with lifecycle projection
  - `initialize_plugin()`
  - `activate_plugin()`
  - `pause_plugin()`
  - `stop_plugin()`
  - `unload_plugin()`
  - `export_plugin_lifecycle()`

## Lifecycle states

```text
registered → initialized → active → paused → active
                          └────────→ stopped → unloaded
```

Invalid transitions are rejected and recorded as lifecycle events.

## Architecture rule

Sprint 38 still does not import or execute plugin entrypoints.

Lifecycle is metadata-first:

```text
Plugin Loader
      │
Plugin Lifecycle Manager
      │
Component Registry
      │
Runtime API
```

This keeps Plugin SDK evolution deterministic, observable and reversible.
