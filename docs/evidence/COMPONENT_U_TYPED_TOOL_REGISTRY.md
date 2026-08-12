# Component U Evidence: Typed Tool Registry and Deterministic Execution

Date: 2026-08-12 | Outcome: TESTED

Qualification covers frozen MCP contract loading, schema meta-validation, unique sorted
registration, separate handler binding, bounded canonical payloads, input/output format
validation, effect-aware policy denial and approval blocking, timeout and safe handler
failure, idempotent replay, changed-input replay rejection, and installed-wheel execution.

Verified: 203 tests; Ruff; strict mypy; schema/contracts; sdist/wheel builds; and an
offline fresh-installed-wheel policy-gated tool execution smoke passed.

