# ACA Web Demo Deployment Guide

This guide describes how to run the ACA public web demo without adding business logic to the web interface. The web layer is only an adapter over the deterministic ACA Runtime.

## Runtime contract

- Runtime: Python 3.10+
- Startup command: `python tools/aca_web.py --host 0.0.0.0`
- Local command: `python tools/aca_web.py --host 127.0.0.1 --port 8765 --open`
- Port source: `PORT` environment variable, with `8765` as local fallback
- Healthcheck: `GET /health`
- Studio route: `GET /studio`
- Demo route: `POST /demo/domain-flow`
- Default Domain Pack root: `examples/domain_packs`
- Default Domain Pack: `customer_support`
- External AI dependency: none

## Required environment

The public demo should run with these environment values unless a platform overrides them:

```text
ACA_HOST=0.0.0.0
PORT=<platform provided port>
ACA_PUBLIC_BASE_URL=<public https base url>
ACA_DOMAIN_PACK_ROOT=examples/domain_packs
ACA_DEFAULT_DOMAIN_PACK=customer_support
ACA_STUDIO_PATH=studio/index.html
```

`ACA_PORT` may be set to `8765` for local usage, but public platforms should prefer `PORT`.

## Local verification

From the repository root, run:

```powershell
python -m pytest -q
python tools/aca_public_demo.py --validate --runtime-adapter
python tools/aca_web.py --host 127.0.0.1 --port 8765 --open
```

Then open:

```text
http://127.0.0.1:8765/studio
```

Manual smoke checks:

```text
GET  http://127.0.0.1:8765/health
GET  http://127.0.0.1:8765/runtime/status
GET  http://127.0.0.1:8765/studio/binding
GET  http://127.0.0.1:8765/public-demo/runtime-adapter
POST http://127.0.0.1:8765/demo/domain-flow
```

Example demo body:

```json
{
  "message": "Necesito ayuda con un reclamo",
  "pack_name": "customer_support",
  "root": "examples/domain_packs"
}
```

## Public platform requirements

A compatible web platform must support:

1. Python 3.10 or newer.
2. A long-running web process.
3. A dynamic port exposed through `PORT`.
4. HTTP health checks.
5. Serving local repository files at runtime.

The platform command should be:

```bash
python tools/aca_web.py --host 0.0.0.0
```

The platform healthcheck should be:

```text
GET /health
```

## Acceptance criteria

The public demo is ready when all of these are true:

- `python -m pytest -q` passes.
- `python tools/aca_public_demo.py --validate --runtime-adapter` returns valid JSON with `valid: true`.
- `/health` returns `status: ok`.
- `/studio` renders Studio HTML.
- `/public-demo/runtime-adapter` returns `public_demo_runtime_adapter.v1`.
- `/demo/domain-flow` returns deterministic output using a local Domain Pack.
- The web adapter does not contain domain business logic.

## Non-goals for Sprint 56

- No visual redesign.
- No external LLM provider.
- No platform-specific vendor lock-in.
- No change to RC1 Core internals.
