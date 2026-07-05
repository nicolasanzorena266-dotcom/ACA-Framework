# Sprint 62 — Hosted Studio Asset Strategy

Sprint 62 adds a hosted asset strategy for ACA Studio.

The goal is to make the hosted demo path explicit about which assets are served,
which routes expose the Studio shell, what fallback behavior is expected, and how
a hosting adapter should report missing files without hiding the failure behind a
blank page.

## Added

- `aca_os/hosted_studio_assets.py`
- `/hosting/studio-assets`
- `/hosting/studio-assets/validate`
- hosting target route declarations for Studio assets
- hosted runtime healthcheck integration for asset strategy validation
- tests for strategy construction, validation, REST routing and hosting contract integration

## Non-goals

- no platform-specific deployment
- no visual redesign
- no runtime business logic inside Studio assets
- no external AI requirement

## Validation

```bash
python -m pytest -q
```
