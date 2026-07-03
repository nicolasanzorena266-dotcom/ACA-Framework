# ACA Framework

ACA Framework is an engineering framework for designing cognitive agents.

ACA is not a chatbot template and it is not a prompt collection. It separates cognition into explicit, auditable layers.

## Core architecture

```text
Event
  â†“
Conversation Manager
  â†“
Mission Manager
  â†“
Policy Manager
  â†“
Compiler
  â†“
Operation Graph
  â†“
ACA Kernel
  â†“
CSM Timeline
  â†“
ACAOutput
```

## Status

RC1 Core is closed.

The repository is the single source of truth for ACA Framework.
Older ZIP prototypes are historical artifacts.

## Quick start

Run from the repository root:

```powershell
python tools/aca_cli.py --message "Que es la franquicia?"
```

With memory persistence:

```powershell
python tools/aca_cli.py --message "Me chocaron ayer" --memory .aca/memory.json
```

Run smoke validation:

```powershell
python tools/smoke_rc1.py
```

Run tests:

```powershell
python -m pytest
```

## Developer boundary

```python
from sdk.factory import process_message

result = process_message("Que es CLEAS?")
```

## What is next

See:

- `docs/RC1_CORE_CLOSED.md`
- `docs/NEXT_PHASES.md`