# RAD Forge / NEXUS OS Engineering Instructions

Owner and originator: Bernard Kwadwo Essuman.

## Mission

Implement the frozen specifications in `docs/specifications/` as a provider-neutral,
evidence-driven autonomous work runtime. Specifications and machine-readable
contracts are authoritative; prompts and provider claims are not.

## Required workflow

For every component: specify, design, contract-test, implement, unit-test,
integration-test, security/failure-test, record evidence, update
`docs/runbooks/STATUS.md`, and commit a focused change. Stop at a failed gate.
Never weaken tests or acceptance criteria to obtain a pass. Acceptance changes
require an ADR.

## Invariants

- Core packages must not import vendor SDKs. Providers live behind adapters.
- LLM output is untrusted input and must be schema-validated.
- Deterministic work is performed by deterministic code.
- Secrets are opaque references; never persist resolved secret values.
- Sensitive, destructive, costly, publishing, external-communication, and
  production actions require policy evaluation and human approval.
- Repair is bounded by attempt, time, and budget limits.
- Capability promotion is derived only from verified evidence.
- Every durable state transition is atomic, observable, and resumable.
- Workspace and network access are deny-by-default and policy-scoped.

## Source-of-truth order

1. Accepted ADRs
2. `docs/specifications/ACCEPTANCE_SPEC.md`
3. Machine-readable files in `schemas/` and `contracts/`
4. Other specifications and architecture documents
5. Runbooks and examples

If sources conflict, stop, document the conflict, and resolve it with an ADR.

## Safety

Never deploy, publish, spend money, contact external users, modify production
data, delete user data, weaken security, or expose credentials without explicit
approval. Preserve user work and inspect diffs before modifying overlapping files.

## Commands

Use `uv sync --all-groups` for development setup and `uv run pytest` for tests.
Additional commands are documented in `docs/runbooks/IMPLEMENT.md`.

