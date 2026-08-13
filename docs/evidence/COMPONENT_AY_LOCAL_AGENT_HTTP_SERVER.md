# Component AY — Local Agent HTTP Server Evidence

Date: 2026-08-13

## Scope

This record covers the loopback-only HTTP transport, local password-derived
operator authentication, in-memory bearer sessions, executable bootstrap, and
the security/failure boundaries frozen in
`docs/specifications/LOCAL_AGENT_HTTP_SERVER.md`.

## Threats exercised

- public-interface binding and DNS-rebinding-style Host values;
- plaintext credential or durable session-token storage;
- wrong credentials, brute-force attempts, duplicate bootstrap, and session
  exhaustion;
- oversized, malformed, or wrongly typed request bodies;
- unsafe password-file permissions and ambiguous factory references;
- process shutdown with an active loopback listener.

## Verification

Focused verification initially passed 8 behavioral tests and strict mypy. Ruff
reported import/order cleanup and explicit test-fixture security annotations; the
reported issues were corrected without changing an acceptance criterion.

The final gates passed:

- `uv run python scripts/validate_contracts.py` — schema, examples, graph, and
  Agent semantics passed;
- `uv run pytest -q` — 445 passed;
- `uv run ruff check .` — passed;
- `uv run mypy src scripts` — 50 source files passed;
- `uv build` — source distribution and wheel built;
- fresh virtual-environment wheel install, `nexus-agent-serve --help`, and
  installed transport/authentication imports — passed.
- exact release pipeline, `scripts/release_evidence.py`, including Python and
  TypeScript gates, clean-room checks, audits, and generated evidence — passed.

The first hosted PR run stopped at the formatting gate because three new files
had not been processed by `ruff format`; behavior, typing, and lint had passed.
The files were formatted, the exact release pipeline passed locally, and a new
hosted run was required before integration.

## Limitations

The transport is intentionally local-only and non-live. It does not make any
provider call, expose a public service, issue TLS certificates, or establish
production readiness. Bearer sessions are single-process and intentionally do
not survive restart. Application/model assembly is an explicit local factory
until the next configuration stage.
