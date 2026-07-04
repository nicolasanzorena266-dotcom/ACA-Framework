# Sprint 44 — Human Test Demo

Sprint 44 closes EPIC 4 by adding a deterministic human-facing demo over the Runtime Interface layer.

## Scope

- Adds a transport-neutral human demo runner.
- Exposes the demo through Runtime API endpoints.
- Exposes the demo through the REST adapter.
- Adds CLI access for a human tester.
- Keeps all domain and execution behavior inside the Runtime.

## Runtime Interface additions

- `GET /demo/human-test`
- `POST /demo/human-test`

The demo uses the existing Runtime API request boundary. It does not import internal Runtime components, does not call plugins directly, and does not contain business logic.

## CLI

```bash
python tools/aca_demo.py
python tools/aca_demo.py --format markdown
```

## Validation

```bash
python -m pytest -q
```

Expected result for this sprint:

```text
172 passed
```
