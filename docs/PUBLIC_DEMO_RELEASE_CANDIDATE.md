# ACA Studio Public Demo Release Candidate

This document freezes the first public demo release candidate for ACA Studio.

## Target

- Surface: ACA Studio
- Platform target: Render Web Service
- Runtime: deterministic ACA Runtime
- External AI dependency: none
- Healthcheck: `/health`
- Studio route: `/studio`
- Runtime status: `/runtime/status`

## Release gates

Before opening the Render public URL as the first demo, the repo must pass:

```powershell
python -m pytest -q
```

After Render publishes the service URL, run:

```powershell
python tools/aca_smoke_url.py https://<render-service>.onrender.com
```

The public smoke test validates health, Studio bootstrap, Studio page, public demo manifest, runtime status and demo Domain Pack execution.

## Start command

```bash
python tools/aca_web.py --host 0.0.0.0
```

Render provides the `PORT` environment variable. ACA falls back to `8765` only for local-style hosts.

## Non-goals

This release candidate does not automate Render account setup, secrets, production SLA, paid hosting or provider APIs.
