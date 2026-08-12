# Threat Model

## Assets and boundaries

Assets include credentials, user code/data, research data, repositories, provider
accounts, state, artifacts, approvals, evidence, and the integrity of qualification.
Trust boundaries exist at every public API, workspace, subprocess, provider, MCP
server, secret backend, persistence system, CI runner, and human approval surface.

## Principal threats and controls

| Threat | Representative controls |
|---|---|
| Prompt/repository injection | Treat content as data; policy cannot be overridden by task text; structured outputs |
| Secret theft or leakage | Reference-only config, scoped resolution, redaction/canaries, restricted subprocess env |
| Path traversal/symlink escape | Canonical path checks, root-scoped handles, race-resistant open strategy |
| Unauthorized side effect | Effect classification, policy, exact-digest approval, idempotency |
| Provider compromise/malformed output | Adapter validation, timeouts, isolation, conformance tests, safe fallback |
| Evidence tampering | Append-only hash chain, digests, verifier, protected storage/export |
| Qualification forgery | Deterministic rules; actor cannot directly promote trust states |
| Infinite/costly execution | Attempt/time/token/cost bounds and cancellation |
| Replay/confused deputy | Project-scoped identity, nonces, expiry, idempotency keys, audience checks |
| Dependency/supply-chain attack | Locked dependencies, provenance/SBOM, isolated build, review and scanning |
| Denial of service | Quotas, rate limits, bounded payload/output, leases and backpressure |

## Assumptions and residual risk

The host and configured secret backend are trusted in the initial local deployment.
Hash chaining detects alteration but does not prevent deletion without external
anchoring or protected storage. Models remain fallible; evidence demonstrates
performed checks, not universal correctness. Production qualification requires a
formal security review and deployment-specific threat-model update.

