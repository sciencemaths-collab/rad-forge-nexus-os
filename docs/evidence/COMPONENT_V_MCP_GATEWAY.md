# Component V Evidence: MCP Gateway

Date: 2026-08-12 | Outcome: TESTED

Qualification covers strict JSON-RPC envelopes, deterministic tool discovery, frozen
contract execution, trusted context/scopes, identity override rejection, policy/schema
execution through Component U, trace and action-digest propagation, stable safe errors,
request bounds, per-actor quotas, and metadata-only audit records.

The gate also corrected Component U's idempotency interpretation: descriptors that
explicitly declare an `idempotency_key` use it and bind it to input; idempotent read-only
tools without that field use the canonical input digest. The complete regression passed.

Verified: 211 tests; Ruff; strict mypy; schema/contracts; sdist/wheel builds; and an
offline fresh-installed-wheel JSON-RPC `tools/list` smoke passed.

