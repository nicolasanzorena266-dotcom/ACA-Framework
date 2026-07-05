# Sprint 55 — Public Demo Runtime Adapter

## Goal

Prepare ACA's public demo runtime adapter contract without moving Runtime behavior into the web layer.

## Added

- Public demo runtime adapter contract.
- Environment-driven adapter builder.
- Adapter validation over the existing public demo readiness contract.
- Runtime API and REST endpoints for adapter discovery and validation.
- CLI support through `tools/aca_public_demo.py --runtime-adapter`.

## Endpoints

- `GET /public-demo/runtime-adapter`
- `GET /public-demo/runtime-adapter/validate`

## Non-goals

- No visual redesign.
- No external LLM dependency.
- No platform-specific deploy lock-in.
- No business logic in the web adapter.
