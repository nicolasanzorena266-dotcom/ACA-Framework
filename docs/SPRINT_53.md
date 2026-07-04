# Sprint 53 — Deployable Web Package

Sprint 53 prepares ACA Web Runtime for external deployment without moving runtime behavior into deployment wrappers.

## Scope

- Adds a deployable web package contract for ACA Studio + Runtime REST.
- Defines stable process command, port environment, healthcheck, routes and required files.
- Adds a small deploy helper CLI to print, validate and write the package JSON.
- Adds `/deploy/package` and `/deploy/validate` to the transport-neutral Runtime API and REST adapter.
- Teaches the local web launcher to read `PORT`, `ACA_PORT` and `ACA_HOST` environment defaults.

## Non-goals

- No hosted deployment is created in this sprint.
- No cloud-provider-specific dependency.
- No LLM dependency.
- No business/domain logic inside deployment helpers.
- No RC1 core mutation.

## Commands

Local run:

```powershell
python tools/aca_web.py --host 127.0.0.1 --port 8765 --open
```

Deploy-style run:

```bash
PORT=8765 python tools/aca_web.py --host 0.0.0.0
```

Print package:

```powershell
python tools/aca_deploy.py --validate
```

Write package:

```powershell
python tools/aca_deploy.py --validate --write deploy/aca-web-package.generated.json
```

## Runtime endpoints

```http
GET /deploy/package
GET /deploy/validate
```

## Validation

Sprint-specific validation:

```text
8 passed
```
