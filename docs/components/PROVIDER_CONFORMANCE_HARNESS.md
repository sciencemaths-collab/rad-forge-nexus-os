# Component R: Provider Conformance Harness

Status: TESTED | Boundary contract: 1.0

The harness executes a fresh provider-neutral `AgentAdapter` instance for each
bounded case and emits an immutable, canonical, SHA-256-addressed report. The fixed
suite covers typed health/capability discovery, successful normalized lifecycle,
contiguous event sequencing, task/trace identity, terminal event/result agreement,
idempotent cancellation, capability-gated resume, and safe unknown-task rejection.

Each adapter operation and event stream is guarded by a finite timeout. Unexpected
adapter exceptions, hangs, malformed identities, broken sequences, and inconsistent
terminal state fail the relevant case without copying provider exception text or task
input into the report. A complete passing deterministic run derives only
`mock_verified`; failure derives `unverified`.

The harness does not issue `live_verified` or `production_qualified`. It does not by
itself prove network/workspace containment, policy enforcement, provider uptime,
vendor-version compatibility, billing accuracy, or production reliability. Live
adapters, policy/sandbox integration, operational evidence, and release approval
remain later component and integration gates.

