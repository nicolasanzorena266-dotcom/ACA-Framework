# RC1 Validation

## Test suite

Run:

```powershell
python -m pytest
```

or:

```powershell
.\tools\run_tests.ps1
```

## Smoke test

Run:

```powershell
python tools/smoke_rc1.py
```

Expected behavior:

- greeting returns a response;
- auto claim creates an `auto_claim_guidance` mission;
- CLEAS and franquicia trigger domain concept lookup;
- indemnizacion / expediente status escalates instead of inventing;
- memory can persist into `.aca/smoke_memory.json`.

## RC1 pass criteria

RC1 Core is considered closed when:

- all tests pass;
- CLI returns valid JSON;
- Galicia domain pack loads;
- runtime returns `ACAOutput`;
- memory persistence works;
- escalation policy blocks real-claim status answers.