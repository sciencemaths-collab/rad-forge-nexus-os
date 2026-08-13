# Component AH Evidence: NEXUS Agent Contracts

Date: 2026-08-13 | Outcome: CLEAN-ROOM QUALIFIED (CONTRACT BOUNDARY ONLY)

Component AH freezes the separation between the user-facing NEXUS Agent, the
governing NEXUS OS runtime, and replaceable reasoning providers. It adds no model
inference, agent controller, tool execution, application service, UI, deployment,
or production capability.

Verified locally:

- Four Draft 2020-12 schemas for candidate specifications, events, sessions, and
  model qualification
- Three valid examples plus semantic lifecycle, uniqueness, review-readiness, and
  privilege-qualification checks
- Separate OpenAPI 3.1.1 agent contract with idempotent mutation boundaries
- Rejection of literal-secret inputs, unknown direct-execution payloads, illegal
  transitions, state/history mismatch, duplicate acceptance identifiers, and
  unsafe privileged model promotion
- Existing frozen NEXUS OS Control API remains unchanged and its dispatcher
  integration contract continues to pass
- Full Python suite: 293 passed
- TypeScript suite: 6 passed
- Ruff format/lint, strict mypy, schema validation, Python distributions, and
  TypeScript package dry-run passed
- Portable Python and npm dependency audits passed with no known third-party
  vulnerabilities
- Isolated locked installation, all 15 automated gates, and independent review
  passed with zero findings

Generated release and clean-room reports record authoritative digests. Hosted CI
and a focused remote commit remain required before this boundary is considered
integrated into the public repository. Qualification applies only to the frozen
contracts and does not promote an agent implementation or production capability.
