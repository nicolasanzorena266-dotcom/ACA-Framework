# Sprint 52 — Demo Domain Runtime Flow

Sprint 52 adds a human-testable domain flow demo over the existing Runtime API surface.

## Scope

- Adds a deterministic demo runner for Domain Pack-backed runtime flows.
- Exposes `/demo/domain-flow` through the transport-neutral Runtime endpoint API.
- Exposes the same scenario and run contract through REST.
- Wires ACA Studio to call the demo domain flow from the browser.
- Keeps domain behavior data-driven through loaded Domain Pack assets.

## Non-goals

- No LLM integration.
- No domain code imports from packs.
- No business logic inside REST or Studio.
- No mutation of RC1 core contracts.

## Local usage

Start the local web runtime:

```powershell
python tools/aca_web.py --host 127.0.0.1 --port 8765 --open
```

Open:

```text
http://127.0.0.1:8765/studio
```

Try:

```text
Check ticket 12345 status
What documents are missing for case 9988?
This is urgent, escalate ticket 7711 because the client is blocked
Where is the bottleneck in onboarding process?
```

## API

```http
GET /demo/domain-flow
POST /demo/domain-flow
```

Example body:

```json
{
  "message": "Check ticket 12345 status",
  "conversation_id": "local-demo",
  "root": "examples/domain_packs"
}
```

## Validation

Sprint-specific validation:

```text
6 passed
```

The full suite reaches the end of execution in sandbox but the process does not exit cleanly in this environment, matching the previously observed local-tooling hang. User-side PowerShell validation remains the source of truth before commit.
