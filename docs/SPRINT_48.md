# Sprint 48 — Example Domain Packs

Sprint 48 adds bundled, data-only Domain Pack examples that exercise the Domain Pack contract, loader and validator without coupling domain content to Runtime internals.

## Added

- `examples/domain_packs/customer_support`
- `examples/domain_packs/operations_basic`
- `aca_os/domain_pack_examples.py`
- `tests/test_example_domain_packs.py`

## Design rules preserved

- Example packs are manifest-first and data-only.
- Example packs do not include Python entrypoints.
- Loading examples goes through `DomainPackLoader` and `ComponentRegistry`.
- Validation goes through `DomainPackValidator`.
- Runtime Core behavior is not modified.

## Validation

```bash
python -m pytest -q
```

Expected Sprint 48 result:

```text
209 passed
```
