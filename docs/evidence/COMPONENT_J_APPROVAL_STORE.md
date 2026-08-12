# Component J Evidence: Durable Approval Store

Date: 2026-08-12 | Outcome: TESTED

Qualification covers durable restart, exact action scope, explicit decisions,
expiration, denial/revocation, atomic one-use consumption, replay rejection,
non-consumption on mismatch, and concurrent-consumer exclusion.

Verified: 121 tests; Ruff; strict mypy; schema/contracts; sdist/wheel builds; and a
strictly offline fresh-environment installed-wheel import all passed.
