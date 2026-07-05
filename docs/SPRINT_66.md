# Sprint 66 — Public URL Smoke Test

Adds a deterministic public URL smoke test layer for ACA hosted demos.

## Goal

When Render provides a public URL, ACA can validate the deployed service without guessing:

- platform health
- runtime status
- Studio page
- Studio bootstrap contract
- public demo manifest
- demo Domain Pack flow

## Command

```powershell
python tools/aca_smoke_url.py https://aca-public-web-demo.onrender.com --validate
```

Plan only, without network calls:

```powershell
python tools/aca_smoke_url.py https://aca-public-web-demo.onrender.com --plan
```

## Scope

This sprint does not deploy ACA. It prepares the hosted URL verification step used after Render creates the public endpoint.
