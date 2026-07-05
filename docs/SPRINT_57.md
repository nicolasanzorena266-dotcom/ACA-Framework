# Sprint 57 — Studio UX Structure

Sprint 57 introduces a stable Studio UX structure for the public demo layer.

## Added

- `aca_os/studio_ux_structure.py` with a declarative Studio UX contract.
- `/studio/ux` Runtime API and REST route.
- A light operational Studio shell inspired by CX Lab-style workspace structure.
- Sidebar navigation, metric cards, simulation workspace, context panel, output panel, trace/metrics space.
- Tests for UX contract, REST route and web shell serving.

## Design boundary

This sprint defines structure, not final visual identity.

The chosen direction is:

- light interface
- fixed sidebar
- operational dashboard layout
- large cards
- blue/violet accents
- Runtime-first data binding

Final tokens, branding and polish remain for Sprint 58.

## Architecture rule

Studio remains an interface. It does not own business logic. Runtime API remains the source of truth.
