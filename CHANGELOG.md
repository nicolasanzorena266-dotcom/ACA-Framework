# Sprint 72A — ACA Platform Plugin Architecture

- Added business-agnostic `aca_core` platform plugin primitives.
- Added `aca_plugin_sdk` public surface for plugin authors.
- Added versioned plugin manifests, loader, registry, capability registry and capability router.
- Added separated CorePolicy / DomainPolicy, isolated plugin state, plugin trace and eval hooks.
- Added `generic.open_chat` fallback plugin and migrated `galicia.insurance` into `plugins/`.
- Added tests for plugin removal, mock plugin installation, trace/state isolation and Core anti-contamination.
## 0.3.0-sprint71-rc10 â€” LLM-assisted Conversational Workflow Runtime

- Added structured public conversation contracts for semantic understanding, policy authorization, planning, supervision and traces.
- Added an offline deterministic fallback that follows the same workflow contract without requiring external LLM access.
- Added public/developer trace separation for the hosted Studio conversation runtime.
- Extended public conversation state with known facts, missing facts, interaction signals, control state, next action and response signature.
- Added multi-turn tests for post-denunciation claim follow-up, contextual deadlines, documentation follow-up, repetition repair and handoff summary.
- Preserved the rule that tools must be explicitly available before ACA can claim operational lookup.

# Changelog


## 0.3.0-sprint71-rc8 â€” Public Conversation Runtime Compatibility Fix

- Fixed typo-tolerant capability and AI-limit detection for realistic user input such as â€œhaceeerâ€ and â€œtenees IAâ€.
- Ensured AI-limit answers preserve active ticket context and still describe real capabilities.
- Restored compatibility with the legacy `test_public_conversation_runtime.py` expectations without reintroducing dashboard cards.
- Adjusted the public Studio layout marker to the single conversation surface expected by Sprint 71 tests.


## 0.3.0-sprint71-rc7 â€” Public Conversation Runtime Hardening

- Hardened the public conversation runtime against isolated-turn fallback behavior.
- Added context-aware documentation answers for franquicia and other siniestro follow-ups.
- Added client-facing example responses for frustration and â€œshow me how it would answerâ€ flows.
- Simplified the hosted Studio public layout into a single centered chat-first surface.

## 0.3.0-sprint71 â€” Public Studio Runtime Interaction QA

- Added RC5 adaptive public conversation state: active ticket, active claim type, goal, topic and fallback/confusion counters.
- Preserved context across turns so short follow-ups continue the active ticket or siniestro instead of restarting.
- Added adaptive representative replies for greetings, capabilities, AI-limit questions, confusion and Galicia-style documentation follow-ups.
- Adjusted Studio layout toward a chat-first story-sized conversation surface without visible dashboard cards.

- Added RC3 conversation-quality correction: identity/capability questions now receive direct human-readable answers.
- Enlarged the phone conversation shell to real cellphone proportions with internal chat scrolling.
- Removed visible `<max-depth>` leaks from module names and replaced the public demo action with **Probar ejemplo**.

- Converted the public Studio conversation into a chat-first interaction with a real send action.
- Constrained the conversation area to scroll inside the phone panel instead of expanding the page indefinitely.
- Made refresh reset the visible conversation state.
- Replaced technical public-facing labels with human-readable Spanish labels while keeping compatibility markers for existing tests.
- Improved demo runtime responses so public interactions read like useful agent answers instead of raw routing diagnostics.


## 0.3.0-sprint70 â€” Public Demo Usability Fix

- Replaced visible raw JSON in ACA Studio runtime context with human-readable summaries.
- Added the **Ver pensamiento** modal for full runtime evidence with explicit close control.
- Connected Studio controls to real refresh/run/copy/navigation behavior.
- Added a human-facing runtime response projection while retaining raw response evidence.

## 0.3.0-sprint66 â€” Public URL Smoke Test

- Added public hosted URL smoke test contract and runner.
- Added `tools/aca_smoke_url.py` for Render/public demo validation.
- Added deploy metadata for post-hosting URL checks.
- Documented Sprint 66 public URL validation workflow.

## Sprint 65 â€” Render Deployment Config

- Added Render deployment configuration contract.
- Added repository-root `render.yaml` blueprint for ACA Studio public demo.
- Added Render deployment guide and deterministic config JSON.
- Added tests for Render start command, healthcheck, environment and required files.



## Sprint 64 â€” First Public Hosted Demo

- Added first public hosted demo deployment contract.
- Added Runtime API and REST routes for `/hosted-demo/first` and `/hosted-demo/first/validate`.
- Added deploy config for the first public hosted demo.
- Extended hosted healthcheck, hosting contract and deployment smoke tests with first-demo coverage.


## 0.3.0-sprint62 â€” Hosted Studio Asset Strategy

- Added hosted Studio asset strategy contract.
- Added runtime and REST endpoints for hosted Studio asset validation.
- Integrated hosted Studio asset checks into hosting contract and healthcheck.
- Documented Sprint 62 asset strategy.


## 0.3.0-sprint61 â€” Hosted Runtime Healthcheck

- Added hosted runtime healthcheck contract for public web deployments.
- Exposed `/hosting/healthcheck` and `/hosting/healthcheck/validate` through Runtime API and REST.
- Updated hosting target routes and deployment JSON to include hosted healthcheck paths.
- Added tests covering healthcheck contract, validation, catalog exposure and REST routing.


## 0.3.0-sprint59 â€” Sprint 59 Public Demo Polish

- Added public demo polish contract for ACA Studio.
- Added public demo polish Runtime API and REST endpoints.
- Updated Studio shell copy and public demo panels.
- Added tests for polish contract, validation, REST/API exposure, and web serving.

## Sprint 58 â€” Visual Design System

- Added ACA Studio visual design system contract.
- Locked visual product naming as ACA Studio.
- Added stable color, typography, spacing, shape and elevation tokens.
- Added Studio component style recipes for sidebar, metric cards, simulation phone, context panel and primary actions.
- Exposed `/studio/design` through Runtime API and REST.
- Embedded the design system into `/studio/ux`.
- Refined Studio HTML into the light operational CX-style dashboard direction.


## Sprint 57 â€” Studio UX Structure

- Added declarative Studio UX structure contract.
- Added `/studio/ux` Runtime API and REST route.
- Reworked Studio into a light operational dashboard shell with sidebar, cards, simulation workspace and context/output panels.
- Preserved Runtime-only business logic boundary.
- Added Studio UX structure tests.



## Sprint 52 â€” Demo Domain Runtime Flow

- Added deterministic Domain Pack-backed demo flow runner.
- Exposed `/demo/domain-flow` through Runtime Endpoint API and REST.
- Wired Studio to run the demo domain flow from the local browser.
- Added tests for runner, Runtime API, REST, and web serving behavior.


## Sprint 51 â€” Studio Runtime Binding

- Added Studio Runtime Binding contract for Runtime/API-backed Studio dashboard state.
- Added `/studio/binding` and `/studio/binding/run` endpoints.
- Updated local Studio UI to show runtime status, domain packs, metrics and last execution trace projection.
- Added tests covering binding projection, REST routing and local web server integration.


## 0.3.0-sprint50 - Local Web Runtime Launcher

- Added local web runtime launch plan contract.
- Added `tools/aca_web.py` to serve Studio and Runtime REST API from one localhost process.
- Added stable local Studio, health, status, run and Domain Pack URLs.
- Added CORS headers and browser-open support for local testing.
- Added Sprint 50 documentation and tests.


## 0.3.0-sprint49 - Domain Pack Runtime Integration

- Added Runtime Domain Pack integration boundary.
- Exposed Domain Pack runtime context to execution context bundles.
- Added Runtime API and REST endpoints for Domain Pack load/list/read/context operations.
- Added tests for Runtime, API and REST Domain Pack integration.

# Changelog

## 0.3.0-sprint48 â€” Example Domain Packs

- Added bundled data-only example Domain Packs for customer support and basic operations.
- Added deterministic example Domain Pack catalog helpers.
- Added tests proving bundled examples validate, load and register through runtime boundaries.
- Bumped package version to `0.3.0-sprint48`.


## Sprint 47 â€” Domain Pack Validator

- Added deterministic `DomainPackValidator` boundary.
- Added structured validation issues, results and snapshots.
- Validated runtime compatibility, dependency declarations, asset formats, required assets and JSON assets.
- Integrated Domain Pack Loader with validation before registration.
- Registered `domain_pack_validator` as an observable runtime-owned component.
- Added Sprint 47 documentation and tests.

## Sprint 46 â€” Domain Pack Loader

- Added manifest-first Domain Pack loader.
- Added deterministic Domain Pack discovery and observable load snapshots.
- Added required asset checks at the load boundary.
- Added runtime facade methods for loading/exporting Domain Packs.
- Added tests for discovery, loading, duplicate handling, dependency validation, asset checks and runtime integration.


## 0.3.0-sprint45 â€” Domain Pack Contract

- Added deterministic Domain Pack manifest contract.
- Added domain runtime compatibility, capabilities and structured asset declarations.
- Added Domain Pack Contract projection into Component Registry descriptors.
- Added safe relative asset path validation and duplicate declaration checks.
- Added Sprint 45 contract tests without loading or executing domain code.

## 0.3.0-sprint44 â€” Human Test Demo

- Added deterministic human test demo runner over Runtime APIs.
- Added `/demo/human-test` scenario and run endpoints.
- Added REST and CLI access to the human demo.
- Added markdown output for human-readable manual validation.
- Added tests for Runtime API, REST, CLI and standalone demo tool.

## Sprint 43 â€” Studio API Integration

- Added Studio API client contract that consumes Runtime Interface responses only.
- Added Studio bootstrap/state/run/replay API integration surfaces.
- Added REST routes for `/studio/bootstrap`, `/studio/state`, `/studio/run` and `/studio/replay`.
- Added static Studio shell wired to real Runtime API endpoints.
- Added tests proving Studio has no direct Runtime/component dependency.

## Sprint 42 â€” Runtime API Endpoints

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


## Sprint 40 â€” Stable CLI

- Added Runtime-backed Stable CLI facade.
- Added stable commands for status, components, plugins, run, trace, metrics, Studio and sessions.
- Kept CLI as an input/output interface with Runtime API delegation.
- Added CLI facade and subprocess command contract tests.

## Sprint 39 â€” Example Plugins

- Added repository-hosted Plugin SDK example plugins.
- Added Echo Tool, Context Snapshot and Decision Audit example manifests.
- Added safe future entrypoint modules without changing loader execution semantics.
- Added `aca_os.plugin_examples` catalog, validation and export helpers.
- Added deterministic tests proving examples validate, load and lifecycle-manage as metadata only.

## Sprint 38 â€” Plugin Lifecycle

- Added deterministic Plugin Lifecycle Manager.
- Added plugin lifecycle records, snapshots and events.
- Added lifecycle states: registered, initialized, active, paused, stopped, unloaded and failed.
- Synchronized plugin lifecycle transitions with Component Registry state.
- Added runtime APIs for initialize, activate, pause, stop, unload and lifecycle export.
- Extended Component Registry with paused state and unregister support.
- Added Sprint 38 Plugin Lifecycle tests.


# Changelog


## Sprint 37 â€” Plugin Validator

- Added deterministic Plugin Validator service.
- Added validation reports with error/warning issues.
- Added runtime compatibility, safe entrypoint, hook target and permission allowlist checks.
- Added registry dependency validation before plugin registration.
- Integrated Plugin Loader with Plugin Validator.
- Added `ACAOSRuntime.validate_plugin()`.
- Registered Plugin Validator as a runtime component.
- Added Sprint 37 Plugin Validator tests.

## Sprint 36 â€” Plugin Loader

- Added deterministic Plugin Loader runtime service.
- Added recursive `plugin.json` discovery.
- Added manifest loading through the Plugin Contract boundary.
- Added Component Registry registration for loaded plugins.
- Added duplicate plugin detection and observable failed load results.
- Added `ACAOSRuntime.load_plugins()` and `ACAOSRuntime.export_plugins()`.
- Registered Plugin Loader as a runtime component.
- Added Sprint 36 Plugin Loader tests.


## Sprint 35 â€” Plugin Manifest & Contract

- Started Epic 3 â€” Plugin SDK.
- Added deterministic Plugin Manifest contract.
- Added runtime compatibility, entrypoint, capabilities, permissions and hooks metadata.
- Added Plugin Contract projection.
- Added conversion from plugin manifest to Component Registry descriptor.
- Added validation for unsupported manifest versions and duplicate declarations.
- Added Plugin SDK manifest tests.


## Sprint 34 â€” Studio Evolution

- Evolved ACA Studio from MVP panels into a Runtime Intelligence view model.
- Added Runtime Health, Decision Graph and Component Registry Studio panels.
- Added `build_studio_intelligence()` as a read-only projection over Runtime Introspection.
- Exposed decision graph, action plan, execution flow and execution plan summaries through introspection state summaries.
- Updated Studio HTML export for richer Runtime Intelligence rendering.
- Added Studio Evolution tests and kept the existing Studio export contract compatible.


## Sprint 31 â€” Decision Graph Engine

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

## Sprint 33 â€” Component Registry

- Added typed Component Registry service.
- Added component descriptors with metadata, capabilities, dependencies and lifecycle state.
- Added runtime component auto-registration.
- Added `ACAOSRuntime.export_components()`.
- Updated introspection to consume Component Registry snapshots.
- Added registry lifecycle and runtime integration tests.

## Sprint 32 â€” Metrics Engine

- Added deterministic Metrics Engine.
- Added runtime metrics export API.
- Added counters, gauges, histograms and percentile aggregation.
- Added component-level metrics derived from Execution Trace.
- Integrated metrics into runtime introspection.
- Added Sprint 32 documentation.
## Sprint 54 â€” Public Web Demo Prep

- Added public web demo preparation contract.
- Added public demo readiness validation.
- Added `/public-demo/manifest` and `/public-demo/readiness` Runtime REST endpoints.
- Added `tools/aca_public_demo.py` helper.
- Added `deploy/public-web-demo.json`.


## Sprint 53 â€” Deployable Web Package

- Added deployable ACA Web Runtime package contract.
- Added deployment helper CLI for printing, validating and writing package JSON.
- Added Runtime and REST deploy package endpoints.
- Added environment-driven host/port defaults to the local web launcher.
- Added deploy package tests and Sprint 53 documentation.

## Sprint 55 â€” Public Demo Runtime Adapter

- Added public demo runtime adapter contract.
- Added adapter validation and environment-driven adapter builder.
- Exposed public demo runtime adapter through Runtime API and REST.
- Added CLI support for runtime adapter output.
- Added tests for adapter contract, validation, REST routing and CLI behavior.


## Sprint 56 â€” Web Demo Deployment Guide

- Added public web demo deployment guide.
- Documented local and public runtime startup commands.
- Documented environment variables, routes, healthcheck and smoke checks.
- Extended `deploy/public-web-demo.json` with guide metadata, deployment steps and acceptance criteria.
- Added tests for deployment guide/config alignment.

## Sprint 60 â€” Hosting Target Contract

- Added platform-neutral hosting target contract.
- Exposed hosting target and validation endpoints through Runtime API and REST.
- Added deploy/hosting-target-contract.json for hosted demo preparation.
- Added tests covering contract validation and endpoint routing.

## Sprint 63 â€” Deployment Smoke Tests

- Added platform-neutral deployment smoke test plan and runner.
- Added REST/Runtime API endpoints for smoke test plan, run, and validation.
- Added deploy/deployment-smoke-tests.json for hosted demo readiness checks.
- Extended hosting target contract and hosted runtime healthcheck with smoke test coverage.



## Sprint 68 â€” Public Demo UX QA

- Added deterministic public demo UX QA contract.
- Added validation for first-user public demo experience criteria.
- Exposed `/public-demo/ux-qa` and `/public-demo/ux-qa/validate`.
- Surfaced UX QA in ACA Studio without moving business logic into the interface.


## Sprint 67 â€” Hosted Runtime Hardening

- Added hosted Runtime hardening contract.
- Added REST hardening endpoints.
- Added stable hosted error envelope.
- Added hosted response headers for public deployment surfaces.
- Added tests and deployment hardening config.

- Sprint 68 patch: preserve Visual Design System compatibility marker for existing Studio shell tests on Windows.

