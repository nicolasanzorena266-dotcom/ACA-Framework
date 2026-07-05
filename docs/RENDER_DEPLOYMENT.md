# ACA Studio — Render Deployment

Use this guide for the first public hosted ACA Studio demo on Render.

## Deployment target

ACA is deployed as a Render Web Service using the repository-root `render.yaml` blueprint.

## Commands

Build command:

```bash
python -m pytest -q
```

Start command:

```bash
python tools/aca_web.py --host 0.0.0.0
```

Render provides the `PORT` environment variable. `tools/aca_web.py` already reads `PORT` when `--port` is not supplied.

## Healthcheck

Render healthcheck path:

```text
/health
```

Expected response includes:

```json
{
  "status": "ok"
}
```

## Public routes

- `/studio`
- `/health`
- `/runtime/status`
- `/hosted-demo/first`
- `/deploy/smoke-tests`
- `/deploy/smoke-tests/run`

## Validation

Local validation:

```bash
python -m pytest tests/test_render_deployment_config.py -q
```

Full validation:

```bash
python -m pytest -q
```

## Notes

Render free services may cold-start after inactivity. That is acceptable for the first demo target, not the final production posture.
