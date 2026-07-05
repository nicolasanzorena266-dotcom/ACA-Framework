# Sprint 70 — Public Demo Usability Fix

Sprint 70 turns the first public hosted demo from a technically valid Runtime view into a human-readable ACA Studio experience.

## Goals

- Remove the raw Runtime JSON wall from the primary public Studio view.
- Keep code and implementation details out of the public interface.
- Add a modal-only **Ver pensamiento** view with a close button.
- Make sidebar, Domain Pack, Trace, Metrics, Deploy, demo, diagnostic and refresh controls perform real actions.
- Explain ACA as a deterministic cognitive runtime, not as another chatbot shell.
- Improve the “qué podés hacer” path with a useful capability explanation.

## Added

- `aca_os/public_demo_usability.py`
- `/public-demo/usability`
- `/public-demo/usability/validate`
- `/public-demo/thought`
- Human-first ACA Studio shell with modal thought view.
- Public usability tests for modal behavior, button actions and no-code/no-JSON defaults.

## Boundaries

- Studio does not own runtime or domain business logic.
- The public UI does not expose source code.
- Raw technical detail is not visible by default.
- External AI remains optional and unused by the public demo.

## Validation

Run:

```bash
python -m pytest -q
```
