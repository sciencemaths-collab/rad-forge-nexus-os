# Component AA Evidence: Deterministic Compute Service

Date: 2026-08-12 | Outcome: TESTED

Qualification covers bounded UTF-8 CSV loading, duplicate/invalid header and row-width
rejection, deterministic type inference, schema inspection, summary statistics,
projection, stable sorting with null placement, numeric chart inputs, immutable outputs,
safe hostile-input failures, and complete engine/version/parameter/seed/digest provenance.

Verified: 248 tests; Ruff; strict mypy; schema/contracts; sdist/wheel builds; and an
offline fresh-installed-wheel deterministic CSV/statistics smoke test passed.
