# Sprint 64 — First Public Hosted Demo

Sprint 64 prepares ACA for the first public hosted demo attempt.

The sprint does not call a hosting provider API or publish the service by itself.
It defines the deployment-facing contract that an external Python web host must satisfy before ACA Studio can be opened from a public URL.

## Added

- `aca_os/first_public_hosted_demo.py`
- `/hosted-demo/first`
- `/hosted-demo/first/validate`
- `deploy/first-public-hosted-demo.json`
- deployment smoke coverage for the first public hosted demo contract

## Hosted target

Recommended first target:

- Render Web Service

Required start command:

```bash
python tools/aca_web.py --host 0.0.0.0
```

Required healthcheck path:

```text
/health
```

Expected Studio route:

```text
/studio
```

## Acceptance

- `GET /hosted-demo/first` returns `first_public_hosted_demo.v1`
- `GET /hosted-demo/first/validate` returns `valid: true`
- deployment smoke tests include `/hosted-demo/first`
- hosted demo prep remains deterministic and offline-safe
- no business logic moves into deploy configuration
