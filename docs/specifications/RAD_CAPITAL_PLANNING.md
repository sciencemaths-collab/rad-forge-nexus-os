# RAD Capital Planning 1.0

Status: implemented in Phase 6.

## Contract

The workflow accepts strict UTF-8 JSON containing source identity, UTC observation and expiry
times, unique asset identifiers, expected returns, covariance, current weights, and bounded policy
parameters. It rejects stale, future, overlong, malformed, duplicate-key, non-finite, and
dimensionally inconsistent snapshots before engine routing.

Preparation produces a SHA-256-bound plan naming the exact qualified capability, version,
operation, network policy, source digest, and acceptance checks. Execution requires a current,
one-use `SENSITIVE` approval matching the project, run, and plan digest. RAD Node then routes only
`rad.decision.financial@0.2.0` operation `portfolio.allocate` with network denied.

Completion requires exact engine/request identity, a feasible bounded allocation, utility no worse
than the submitted baseline, `execution_authorized: false`, and a verified four-record evidence
chain. The canonical export contains the structured dossier and complete sealed evidence records.

## Security and product boundary

The workflow performs decision support only. It has no broker, transaction, credential, network,
publishing, or deployment interface. Input freshness proves only that the operator declared a
snapshot current; it does not prove source-system authenticity. External action requires a
separate policy and approval flow that is intentionally absent.

This release is a locally qualified product kernel. Customer outcome validation, governed live
connectors, multi-tenant operations, and production authorization are not inferred from automated
tests.
