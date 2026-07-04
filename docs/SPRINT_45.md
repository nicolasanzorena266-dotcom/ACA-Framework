# Sprint 45 — Domain Pack Contract

## Goal

Define the deterministic Domain Pack manifest boundary for ACA without loading,
executing or coupling domain packs to Runtime internals.

## Added

- `aca_os.domain_pack_manifest.DomainPackManifest`
- `DomainPackRuntimeCompatibility`
- `DomainPackCapability`
- `DomainPackAsset`
- `DomainPackContract`
- `build_domain_pack_contract()`
- Component Registry projection for domain packs
- Contract tests for parsing, JSON roundtrip, file loading, duplicate detection,
  safe asset paths and registry registration

## Rules

- Domain Packs are data contracts first.
- Domain Packs do not import Runtime internals.
- Domain Packs do not depend on components directly.
- Runtime visibility is through `ComponentDescriptor` only.
- Loading and validation remain future Sprint work.

## Validation

```bash
python -m pytest -q
```
