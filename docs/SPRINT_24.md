# Sprint 24 — Developer Experience Commands

## Objective

Add a small zero-cost developer experience layer so ACA can inspect itself from the command line.

This sprint does not change the RC1 Core contract. It adds local tooling around the runtime.

## Added

- `aca_os.dx`
- `aca doctor`
- `aca version`
- `aca inspect runtime`
- `aca test`

The commands are available through the existing local CLI:

```powershell
python tools/aca_cli.py doctor
python tools/aca_cli.py version
python tools/aca_cli.py inspect runtime
python tools/aca_cli.py test
```

The previous message-processing CLI remains valid:

```powershell
python tools/aca_cli.py --message "Que es CLEAS?"
```

## Why this matters

ACA needs to become easier to validate before it becomes larger.

The DX layer gives the project a local, offline health check and an inspectable runtime pipeline without introducing any paid dependency or LLM dependency.

## Validation

Expected test count after this sprint:

```text
55 passed
```
