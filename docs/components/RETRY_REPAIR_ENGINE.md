# Component H: Retry and Repair Engine

Status: TESTED | Decision contract: 1.0

The engine makes deterministic `RETRY`, `REPAIR`, or `STOP` decisions from immutable
attempt history. It applies attempt, elapsed-time, estimated-cost, repeated-failure,
and capped-backoff bounds before permitting more work. Security-policy, cancellation,
and every other non-retryable failure stop immediately.

The engine does not execute repairs or select providers. Policy authorization,
provider fallback, and durable attempt orchestration remain later integration gates.
