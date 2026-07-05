# Sprint 67 — Hosted Runtime Hardening

Adds the hosted Runtime hardening contract for the first public deployment path.

## Added

- Hosted hardening contract for headers, timeouts, body limits and stable errors.
- REST endpoints:
  - `GET /hosting/hardening`
  - `GET /hosting/hardening/validate`
- Hosted-safe response headers on REST responses.
- Stable hosted error envelope for REST failures.
- Deployment config file for the hardening contract.

## Non-goals

- No runtime core rewrite.
- No provider API calls.
- No business/domain logic inside the hosting layer.
- No visual redesign.
