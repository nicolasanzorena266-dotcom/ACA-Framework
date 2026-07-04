# Sprint 43 — Studio API Integration

## Goal

Connect ACA Studio to real Runtime API surfaces without moving business logic into Studio.

## Added

- `aca_os.studio_api.StudioAPIClient` as a transport-neutral Studio API consumer.
- `StudioAPIResource` and `StudioAPIState` contracts.
- Runtime endpoint methods for Studio bootstrap, state, run and replay.
- REST routes:
  - `GET /studio/bootstrap`
  - `GET /studio/state`
  - `POST /studio/run`
  - `POST /studio/replay`
- `studio/index.html` as a minimal browser shell calling the real REST API.

## Rules preserved

- Studio does not instantiate Runtime internals.
- Studio does not inspect components directly.
- Studio consumes Runtime Interface responses.
- Runtime Trace and Introspection remain the source of truth.
- REST remains a thin transport adapter.

## Validation

```bash
python -m pytest -q
```

Expected result for this sprint: `168 passed`.
