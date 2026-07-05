# Sprint 65 — Render Deployment Config

Sprint 65 adds Render-specific deployment configuration for the first public ACA Studio hosted demo.

## Goal

Prepare ACA for a first Render Web Service deployment without moving runtime behavior into hosting files.

## Added

- `render.yaml` blueprint at repository root.
- `deploy/render-deployment.json` deterministic deployment contract.
- `aca_os/render_deployment_config.py` config and validation helpers.
- Tests for Render command, healthcheck, env vars, required files and blueprint content.

## Render baseline

- Service type: `web`
- Runtime: `python`
- Build command: `python -m pytest -q`
- Start command: `python tools/aca_web.py --host 0.0.0.0`
- Healthcheck path: `/health`
- Studio path: `/studio`

## Boundary

Render configuration is deployment metadata only. Runtime logic remains in ACA Runtime and Runtime API services.
