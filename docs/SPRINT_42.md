# Sprint 42 — Runtime API Endpoints

## Goal

Expose a stable Runtime API endpoint layer that can be consumed by REST, Studio, CLI and future adapters without embedding business logic in those interfaces.

## Added

- `aca_os.runtime_api_endpoints.RuntimeEndpointAPI`
- Stable endpoint catalog with explicit capabilities
- Component detail endpoint support
- Generic runtime event processing endpoint
- Plugin loading endpoint
- Plugin lifecycle snapshot endpoint
- Plugin lifecycle transition endpoint
- Studio view endpoint
- Session save endpoint

## REST routes added

- `GET /runtime/components/{name}`
- `GET /runtime/studio`
- `POST /runtime/events`
- `POST /runtime/plugins/load`
- `GET /runtime/plugin-lifecycle`
- `POST /runtime/plugin-lifecycle`
- `POST /sessions/save`

## Architecture

REST remains a thin transport adapter.

RuntimeEndpointAPI owns request-level endpoint normalization and delegates runtime behavior to `ACAOSRuntime` or the SDK factory.

No RC1 Core changes were made.
