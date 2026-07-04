
## 0.3.0-sprint49 - Domain Pack Runtime Integration

- Added Runtime Domain Pack integration boundary.
- Exposed Domain Pack runtime context to execution context bundles.
- Added Runtime API and REST endpoints for Domain Pack load/list/read/context operations.
- Added tests for Runtime, API and REST Domain Pack integration.

# Changelog

## 0.3.0-sprint48 — Example Domain Packs

- Added bundled data-only example Domain Packs for customer support and basic operations.
- Added deterministic example Domain Pack catalog helpers.
- Added tests proving bundled examples validate, load and register through runtime boundaries.
- Bumped package version to `0.3.0-sprint48`.


## Sprint 47 — Domain Pack Validator

- Added deterministic `DomainPackValidator` boundary.
- Added structured validation issues, results and snapshots.
- Validated runtime compatibility, dependency declarations, asset formats, required assets and JSON assets.
- Integrated Domain Pack Loader with validation before registration.
- Registered `domain_pack_validator` as an observable runtime-owned component.
- Added Sprint 47 documentation and tests.

## Sprint 46 — Domain Pack Loader

- Added manifest-first Domain Pack loader.
- Added deterministic Domain Pack discovery and observable load snapshots.
- Added required asset checks at the load boundary.
- Added runtime facade methods for loading/exporting Domain Packs.
- Added tests for discovery, loading, duplicate handling, dependency validation, asset checks and runtime integration.


## 0.3.0-sprint45 — Domain Pack Contract

- Added deterministic Domain Pack manifest contract.
- Added domain runtime compatibility, capabilities and structured asset declarations.
- Added Domain Pack Contract projection into Component Registry descriptors.
- Added safe relative asset path validation and duplicate declaration checks.
- Added Sprint 45 contract tests without loading or executing domain code.

## 0.3.0-sprint44 — Human Test Demo

- Added deterministic human test demo runner over Runtime APIs.
- Added `/demo/human-test` scenario and run endpoints.
- Added REST and CLI access to the human demo.
- Added markdown output for human-readable manual validation.
- Added tests for Runtime API, REST, CLI and standalone demo tool.

## Sprint 43 — Studio API Integration

- Added Studio API client contract that consumes Runtime Interface responses only.
- Added Studio bootstrap/state/run/replay API integration surfaces.
- Added REST routes for `/studio/bootstrap`, `/studio/state`, `/studio/run` and `/studio/replay`.
- Added static Studio shell wired to real Runtime API endpoints.
- Added tests proving Studio has no direct Runtime/component dependency.

## Sprint 42 — Runtime API Endpoints

- Added transport-neutral RuntimeEndpointAPI.
- Added stable runtime endpoint catalog with capabilities.
- Added REST routes for component detail, generic events, Studio view, plugin loading, plugin lifecycle transitions and session saving.
- Added tests for Runtime endpoint behavior and REST routing.

## 0.3.0-sprint41

- Added REST API Foundation as a thin Runtime Interface.
- Added stable transport-neutral REST response contracts.
- Added stdlib HTTP server adapter for local/offline usage.
- Added REST endpoints for health, status, components, plugins, metrics, introspection, run, trace and session replay.
- Added tests for REST service routing, error envelopes and HTTP serving.


## Sprint 40 — Stable CLI

- Added Runtime-backed Stable CLI facade.
- Added stable commands for status, components, plugins, run, trace, metrics, Studio and sessions.
- Kept CLI as an input/output interface with Runtime API delegation.
- Added CLI facade and subprocess command contract tests.

## Sprint 39 — Example Plugins

- Added repository-hosted Plugin SDK example plugins.
- Added Echo Tool, Context Snapshot and Decision Audit example manifests.
- Added safe future entrypoint modules without changing loader execution semantics.
- Added `aca_os.plugin_examples` catalog, validation and export helpers.
- Added deterministic tests proving examples validate, load and lifecycle-manage as metadata only.

## Sprint 38 — Plugin Lifecycle

- Added deterministic Plugin Lifecycle Manager.
- Added plugin lifecycle records, snapshots and events.
- Added lifecycle states: registered, initialized, active, paused, stopped, unloaded and failed.
- Synchronized plugin lifecycle transitions with Component Registry state.
- Added runtime APIs for initialize, activate, pause, stop, unload and lifecycle export.
- Extended Component Registry with paused state and unregister support.
- Added Sprint 38 Plugin Lifecycle tests.


# Changelog


## Sprint 37 — Plugin Validator

- Added deterministic Plugin Validator service.
- Added validation reports with error/warning issues.
- Added runtime compatibility, safe entrypoint, hook target and permission allowlist checks.
- Added registry dependency validation before plugin registration.
- Integrated Plugin Loader with Plugin Validator.
- Added `ACAOSRuntime.validate_plugin()`.
- Registered Plugin Validator as a runtime component.
- Added Sprint 37 Plugin Validator tests.

## Sprint 36 — Plugin Loader

- Added deterministic Plugin Loader runtime service.
- Added recursive `plugin.json` discovery.
- Added manifest loading through the Plugin Contract boundary.
- Added Component Registry registration for loaded plugins.
- Added duplicate plugin detection and observable failed load results.
- Added `ACAOSRuntime.load_plugins()` and `ACAOSRuntime.export_plugins()`.
- Registered Plugin Loader as a runtime component.
- Added Sprint 36 Plugin Loader tests.


## Sprint 35 — Plugin Manifest & Contract

- Started Epic 3 — Plugin SDK.
- Added deterministic Plugin Manifest contract.
- Added runtime compatibility, entrypoint, capabilities, permissions and hooks metadata.
- Added Plugin Contract projection.
- Added conversion from plugin manifest to Component Registry descriptor.
- Added validation for unsupported manifest versions and duplicate declarations.
- Added Plugin SDK manifest tests.


## Sprint 34 — Studio Evolution

- Evolved ACA Studio from MVP panels into a Runtime Intelligence view model.
- Added Runtime Health, Decision Graph and Component Registry Studio panels.
- Added `build_studio_intelligence()` as a read-only projection over Runtime Introspection.
- Exposed decision graph, action plan, execution flow and execution plan summaries through introspection state summaries.
- Updated Studio HTML export for richer Runtime Intelligence rendering.
- Added Studio Evolution tests and kept the existing Studio export contract compatible.


## Sprint 31 — Decision Graph Engine

- Added deterministic Decision Graph Engine.
- Persisted `zero_cost_decision_graph` in runtime facts.
- Added `DECISION_GRAPH` operation to execution trace.
- Added `runtime.decision_graph_created` event bus event.
- Updated runtime introspection and DX inventory.
- Added Sprint 31 documentation.
- Full suite: 89 passing tests.

## RC1 Core Closed

- Added ACA Kernel reference implementation.
- Added ACA OS runtime orchestration.
- Added Conversation Manager.
- Added Mission Manager.
- Added Policy Manager.
- Added Tool Engine.
- Added Context Manager.
- Added Memory Engine.
- Added JSON Memory Store.
- Added ACAOutput boundary.
- Added Galicia Domain Pack v1.
- Added SDK factory.
- Added CLI.
- Added smoke validation.
- Added RC1 validation and closure docs.

## RC1 Core Bootstrap

- Created official repository structure.
- Consolidated Kernel / ACA OS / Domain Pack separation.
- Added core specification.
- Added ADR and RFC structure.
- Added reference Kernel skeleton.
- Added Mission, Policy and Memory OS contracts.

## Sprint 33 — Component Registry

- Added typed Component Registry service.
- Added component descriptors with metadata, capabilities, dependencies and lifecycle state.
- Added runtime component auto-registration.
- Added `ACAOSRuntime.export_components()`.
- Updated introspection to consume Component Registry snapshots.
- Added registry lifecycle and runtime integration tests.

## Sprint 32 — Metrics Engine

- Added deterministic Metrics Engine.
- Added runtime metrics export API.
- Added counters, gauges, histograms and percentile aggregation.
- Added component-level metrics derived from Execution Trace.
- Integrated metrics into runtime introspection.
- Added Sprint 32 documentation.