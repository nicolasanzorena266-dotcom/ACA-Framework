# Sprint 56 — Web Demo Deployment Guide

## Goal

Prepare ACA for public web demo deployment by documenting and verifying the web runtime contract, deployment commands, environment variables, public routes and smoke checks.

## Added

- `docs/WEB_DEMO_DEPLOYMENT.md` with local and public deployment instructions.
- Deployment guide metadata in `deploy/public-web-demo.json`.
- Test coverage for guide presence, required commands, route documentation and deploy config alignment.

## Runtime boundaries

The guide keeps the interface rule intact:

```text
Studio / REST / public web adapter
        │
Runtime API
        │
Runtime Services
        │
Kernel
```

The public demo guide does not move domain behavior into the web layer.

## Validation

Run:

```bash
python -m pytest -q
python tools/aca_public_demo.py --validate --runtime-adapter
python tools/aca_web.py --host 127.0.0.1 --port 8765 --open
```

Expected local Studio URL:

```text
http://127.0.0.1:8765/studio
```

## Non-goals

- No visual redesign.
- No hosted deployment yet.
- No platform-specific lock-in.
- No external AI dependency.
