# Sprint 46 — Domain Pack Loader

## Goal

Add a stable loader for Domain Packs without coupling packs to runtime internals.

## Added

- `aca_os.domain_pack_loader.DomainPackLoader`
- deterministic discovery of `domain_pack.json`
- load results and loader snapshots
- required asset existence checks
- component registry projection for loaded packs
- runtime facade methods:
  - `load_domain_packs`
  - `export_domain_packs`

## Boundary

Domain Packs are metadata and structured assets only at this layer.

The loader does not import domain code, does not execute pack logic, and does not access runtime internals beyond the Component Registry contract.
