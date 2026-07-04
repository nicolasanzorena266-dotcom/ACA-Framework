# Sprint 40 — Stable CLI

## Status

Completed.

## Goal

Provide a stable command-line interface for ACA Runtime Interfaces without
placing business logic inside the CLI script.

## Added

- `aca_os.runtime_cli.RuntimeCLI` as the Runtime-backed CLI command facade.
- Stable CLI commands for:
  - `status`
  - `components list`
  - `plugins list`
  - `run`
  - `trace`
  - `metrics`
  - `inspect runtime`
  - `inspect session`
  - `studio`
  - `session save/show/replay/compare`
- Backward-compatible root `--message` execution path.
- CLI facade tests and subprocess CLI contract tests.

## Architecture Notes

The CLI remains an interface boundary only. Argument parsing and rendering live
in `tools/aca_cli.py`; Runtime behavior is delegated to `RuntimeCLI`, which in
turn consumes public Runtime APIs such as component export, plugin export,
metrics export, trace export, session replay and Studio export.

No RC1 Core behavior was changed.
