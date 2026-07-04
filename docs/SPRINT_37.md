# Sprint 37 — Plugin Validator

Status: completed.

## Goal

Introduce a deterministic Plugin SDK validation layer between plugin manifests and the loader.

ACA must be able to reject unsafe or incompatible plugins before registration, without importing or executing plugin code.

## Added

- `PluginValidator` runtime service.
- `PluginValidationReport` export contract.
- `PluginValidationIssue` with error/warning severity.
- Runtime compatibility validation.
- Safe entrypoint validation.
- Hook target validation.
- Permission allowlist validation.
- Registry dependency validation.
- Loader integration before component registration.
- Runtime validation API: `ACAOSRuntime.validate_plugin()`.
- Component Registry visibility for `plugin_validator`.

## Contract

```text
Plugin Manifest
      │
Plugin Validator
      │
Plugin Loader
      │
Component Registry
      │
Runtime API
```

The validator remains metadata-only. It never imports plugin modules and never executes plugin entrypoints.

## Test coverage

Full suite validated:

```text
126 passed
```
