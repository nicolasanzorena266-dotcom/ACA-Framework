# Sprint 49 — Domain Pack Runtime Integration

Sprint 49 connects validated Domain Packs to the Runtime as deterministic, observable context.

## Added

- `aca_os.domain_pack_runtime` as the runtime integration boundary for Domain Packs.
- Runtime-level Domain Pack context export through `ACAOSRuntime.export_domain_pack_context`.
- Individual Domain Pack read access through `ACAOSRuntime.get_domain_pack`.
- Runtime API endpoints for Domain Pack listing, loading, reading and context export.
- REST routes mirroring the transport-neutral Runtime API.

## Guarantees

- Domain Packs remain data-only.
- Runtime integration reads JSON/text assets but never imports pack Python code.
- Domain context is attached through `ContextManager` and visible in execution output.
- Interfaces remain thin adapters over Runtime API.
