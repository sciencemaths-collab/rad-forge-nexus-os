# Component B Evidence Record

Recorded: 2026-08-12 | Outcome: PASS | Qualification: TESTED

Scope: provider-neutral identifiers, enums, task definitions and graph containers,
commands, normalized events/results/failures, artifact references, immutable JSON
payloads, canonical serialization, and construction-time failure behavior.

## Reproducible checks

| Check | Result |
|---|---|
| `uv run ruff check .` | PASS |
| `uv run mypy src scripts` | PASS; 4 source files |
| `uv run python scripts/validate_contracts.py` | PASS |
| `uv run pytest -q` | PASS; 47 tests |
| `uv build` | PASS; sdist and wheel |
| Fresh environment wheel install | PASS |
| Installed-wheel domain import/identifier smoke | PASS |

Security/failure coverage rejects invalid typed identifiers, non-JSON custom
objects, non-string mapping keys, NaN/infinity, invalid artifact locations and
digests, illegal retry hints, contradictory results, naive timestamps, and
unbounded or absent idempotency keys.

Graph cycle and unknown-dependency behavior is not claimed by this component; it
remains assigned to the graph validator. This is a checked-in provisional evidence
record, not a Component M cryptographic evidence-ledger record.
