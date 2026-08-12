# Component C Evidence Record

Recorded: 2026-08-12 | Outcome: PASS | Qualification: TESTED

Scope: deterministic run/task transition tables, terminal-state protection,
cancellation staging, failure metadata guards, immutable transition records, and
validation of sequence/time/reason metadata.

## Reproducible checks

| Check | Result |
|---|---|
| `uv run ruff check .` | PASS |
| `uv run mypy src` | PASS; 4 source files |
| `uv run python scripts/validate_contracts.py` | PASS |
| `uv run pytest -q` | PASS; 63 tests |
| `uv build` | PASS; sdist and wheel |
| Fresh-environment installed-wheel state-machine smoke | PASS |

Contract and security coverage exercises legal paths, illegal skips, terminal
state reopening, cancellation bypass, contradictory failure metadata, invalid
sequence values, non-UTC timestamps, invalid reason tokens, and every run/task
state pair.

Persistence, sequence allocation, compare-and-swap behavior, and crash recovery
are intentionally not claimed. This is a checked-in provisional evidence record,
not a Component M cryptographic evidence-ledger record.
