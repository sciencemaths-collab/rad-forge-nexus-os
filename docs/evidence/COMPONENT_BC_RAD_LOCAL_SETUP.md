# Component BC: RAD Agent Local Setup and Diagnostics

Status: AUTOMATED GATES PASS | Boundary contract: 1.0

## Qualified behavior

Phase 1 introduces the supported `rad` product command:

- `rad setup` discovers fixed loopback OpenAI-compatible endpoints, selects an exact
  reported model, creates schema-valid configuration, and writes owner-only settings and
  operator credential files.
- `rad doctor` checks settings, configuration, permissions, endpoint availability, model
  selection, and operating-mode requirements without invoking inference.
- `rad serve` loads generated settings and starts the existing loopback application.
- Preferred `RAD_AGENT_*` variables and RAD command aliases coexist with legacy identifiers.
- Development mode reports no active qualification and authorizes only candidate
  specification and bounded proposal repair. Runtime tools, tool selection, sensitive uses,
  and production claims remain unavailable.
- Qualified mode retains exact independently attested model enforcement.

## Verification

GitHub Actions run 71 completed successfully on 2026-08-13 for head
`1e2788c5d761cd852412ddd6d908e8de96b70019`.

All 15 automated release gates passed:

- Ruff formatting and lint
- Strict mypy
- Schema and contract validation
- Python and TypeScript dependency audits
- Unit, contract, integration, security, and provider-conformance tests
- Reference workflow
- TypeScript SDK tests
- Offline package build
- Secret scan

Release-evidence artifact digest:
`sha256:13f977a5107b9002cf500a00214c01bf1bf65f1ed7848a47c9ac0b5e6c871a9c`

Final evidence report digest:
`sha256:ddf3bb1b8a4eeb3080aeaaeab64594e9be4e12e92e79a60f9ac4cf8800a5c7e2`

## Limitations

This phase does not download or manage models, connect direct cloud APIs, execute domain
tools, expose a public server, establish live-provider qualification, or make the project
production-ready. Automated gates passing is not owner approval or clean-room production
qualification.
