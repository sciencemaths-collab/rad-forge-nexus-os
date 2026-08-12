# Component S Evidence: OpenAI/Codex Adapter

Date: 2026-08-12 | Outcome: TESTED WITH FAKE TRANSPORT | Live: UNVERIFIED

Qualification covers secret-reference-only construction, scoped credential resolution,
Responses request mapping, `store: false`, background execution, response identity and
status validation, normalized lifecycle/results/usage, idempotent cancellation,
retrieval/resume, duplicate/unknown-task rejection, safe failures, vendor-import and
ambient-environment exclusion, and Component R conformance with an injected transport.

Verified: 188 tests; Ruff; strict mypy; schema/contracts; sdist/wheel builds; and an
offline fresh-installed-wheel descriptor smoke passed. No API credential, live network
request, cost, or provider qualification claim was used or produced.

Official design references reviewed on 2026-08-12:

- https://developers.openai.com/api/docs/guides/streaming-responses
- https://developers.openai.com/api/docs/guides/background

