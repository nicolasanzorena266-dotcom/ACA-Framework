# Sprint 54 — Public Web Demo Prep

Sprint 54 prepares ACA for a public web demo without changing Runtime business logic or visual design.

## Added

- Public Web Demo preparation manifest.
- Public demo readiness validation.
- REST endpoints for public demo manifest and readiness.
- CLI helper for printing/writing public demo metadata.
- Static deploy manifest under `deploy/public-web-demo.json`.

## Boundaries

- No external LLM dependency.
- No platform lock-in.
- No aesthetic redesign.
- No Runtime Core changes.

## Useful commands

```powershell
python tools/aca_public_demo.py --validate
python tools/aca_public_demo.py --public-base-url https://example.com
python tools/aca_web.py --host 0.0.0.0
```
