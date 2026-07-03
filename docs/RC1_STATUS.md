# ACA Framework RC1 Status

## Current state

ACA Framework now has:

- Kernel
- Compiler
- Operation Graph
- Operation Contracts
- Compliance
- Mission Manager
- Policy Manager
- Tool Engine
- Context Manager
- Conversation Manager
- Memory Engine
- JSON memory persistence
- Output boundary
- Galicia Domain Pack v1
- CLI entrypoint
- SDK factory

## What is usable now

A developer can run ACA locally through:

```powershell
python tools/aca_cli.py --message "Que es la franquicia?"
```

or with memory persistence:

```powershell
python tools/aca_cli.py --message "Me chocaron ayer" --memory .aca/memory.json
```

## What is still not RC1-complete

- ACA Studio UI
- stronger CI configuration
- more Galicia scenarios
- packaging as installable Python package
- richer domain policies
- real external adapters