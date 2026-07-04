# Sprint 50 — Local Web Runtime Launcher

## Goal

Provide a stable local web entrypoint that serves ACA Studio and the Runtime REST API from one localhost server.

## Scope

- Added `aca_os.web_runtime_launcher` as a transport-neutral launch plan boundary.
- Added `tools/aca_web.py` to serve Studio HTML and delegate runtime requests to `RuntimeRESTAPI`.
- Added stable local URLs for Studio, health, status, Studio state/run and Domain Packs.
- Added CORS headers for local browser testing.
- Added tests for launch plans, server behavior and CLI plan output.

## Constraints

- No Runtime Core logic was moved into the web launcher.
- The launcher is an I/O adapter only.
- Studio remains static HTML; Runtime behavior stays behind API endpoints.

## Manual usage

```powershell
python tools/aca_web.py --host 127.0.0.1 --port 8765 --open
```

Then open:

```text
http://127.0.0.1:8765/studio
```

Stop with `Ctrl+C`.
