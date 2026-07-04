# Sprint 33 — Component Registry

Component Registry becomes the runtime-owned discovery and contract surface for ACA components.

## Delivered

- Typed `ComponentDescriptor` contract.
- Deterministic `ComponentRegistry` service.
- Lifecycle states: `registered`, `initialized`, `active`, `stopped`.
- Contract validation for required metadata and declared dependencies.
- Runtime component auto-registration.
- Runtime export API: `export_components()`.
- Introspection now reads component inventory from the registry.
- Compatibility with Metrics Engine and Execution Trace preserved.

## Architecture rule

Interfaces consume registry snapshots. They do not inspect component implementations.

```text
Component
      │
Runtime API
      │
Component Registry
      │
Kernel
```

This prepares ACA for Plugin SDK, REST API and MCP without making components depend on each other.
