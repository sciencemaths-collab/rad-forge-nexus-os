# Component B: Core Domain Models

Status: TESTED | Domain contract version: 1.0

## Responsibility and boundary

`nexus_os.domain` defines provider-neutral, immutable values shared by the kernel:
typed run/task/trace identifiers; action, failure, run, task, event, and command
enums; canonical task definitions and graphs; normalized commands, events,
failures, artifact references, and task results.

The module performs construction-time structural validation and defensive freezing.
It does not choose legal lifecycle transitions, compile or semantically validate a
task graph, persist state, resolve secrets, evaluate policy, or invoke providers.
Those behaviors remain assigned to Components C and later.

## Determinism and safety behavior

- UUID, task ID, trace ID, digest, token, artifact URI, timestamp, retry, and
  resource-bound fields fail closed with `DomainValidationError`.
- Payloads accept canonical JSON-compatible values only. Non-string object keys,
  non-finite floats, executable/custom objects, bytes, and mutable caller aliases
  are rejected or defensively frozen.
- Task graphs have order-independent canonical serialization and SHA-256 digests.
  Unknown-dependency and cycle checks are intentionally deferred to the graph
  validator component.
- Security-policy and cancellation failures cannot be marked retryable.
- Results require terminal states and pair a structured failure only with `FAILED`.
- Mutating runtime commands require UUID identity, UTC time, trace context, and a
  bounded non-empty idempotency key.

## Qualification limits

This component is TESTED, not production-qualified. Component C owns legal state
transitions. Components D/E own graph compilation and semantic validation. Later
schema adapters will validate wire payloads before constructing these models, and
the evidence ledger will replace this provisional component record with chained
runtime evidence.
