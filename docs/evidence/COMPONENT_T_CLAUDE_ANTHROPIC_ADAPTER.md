# Component T Evidence: Claude/Anthropic Adapter

Date: 2026-08-12 | Outcome: TESTED WITH FAKE TRANSPORT | Live: UNVERIFIED

Qualification covers secret-reference-only construction, scoped credential resolution,
Messages request mapping, message identity/type/role validation, bounded max tokens,
stop-reason and usage validation, normalized success/truncation/refusal, terminal
cancellation idempotency, explicit unsupported resume, duplicate/unknown-task rejection,
safe failures, vendor-import/ambient-environment exclusion, and Component R conformance.

Verified: 196 tests; Ruff; strict mypy; schema/contracts; sdist/wheel builds; and an
offline fresh-installed-wheel descriptor smoke passed. No API credential, live request,
cost, or provider qualification claim was used or produced.

Official Anthropic API documentation reviewed on 2026-08-12:

- https://docs.anthropic.com/en/api/handling-stop-reasons

