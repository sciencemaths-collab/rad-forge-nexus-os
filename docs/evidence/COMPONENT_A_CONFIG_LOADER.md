# Component A Evidence Record

Recorded: 2026-08-12 | Outcome: PASS | Qualification: TESTED

Scope: configuration loading, overlay, defaulting, validation, canonicalization,
redaction, input failure behavior, and installed-wheel schema availability.

## Reproducible checks

| Check | Result |
|---|---|
| `uv run ruff check .` | PASS |
| `uv run mypy src scripts` | PASS; 3 source files |
| `uv run python scripts/validate_contracts.py` | PASS |
| `uv run pytest -q` | PASS; 20 tests |
| `uv build` | PASS; sdist and wheel |
| Fresh `uv venv` + `uv pip install` wheel | PASS |
| Installed-wheel example load | PASS |
| Packaged `nexus_os/schemas/project.schema.json` inspection | PASS |

Canonical example configuration digest:
`sha256:00b86ae09f88866a13423388fb97429e0c8770ae366817d55269b942a5d350f1`.

The first clean-install attempt intentionally used `pip --no-deps` and stopped on
the absent declared `jsonschema` dependency. It was classified as a test-harness
setup failure. The corrected clean environment installed the wheel with its
declared dependencies and passed. No acceptance criterion or test was weakened.

This is a checked-in provisional evidence record. It is not represented as a
cryptographic evidence-ledger record because Component M does not yet exist.
