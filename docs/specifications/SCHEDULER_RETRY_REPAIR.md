# Scheduler Retry and Repair Integration

Status: Accepted Phase AV boundary | Normative

## Purpose

Phase AV integrates the deterministic retry engine with the Phase AU scheduler without
rewriting the approved graph, task input, or prior failure evidence. Every unsuccessful
tool attempt becomes an immutable durable record before a retry decision is made.

## Attempt evidence

Attempt records are append-only and keyed by run, task, and contiguous attempt number.
They store the sanitized failure classification/code, retryable flag, bounded details,
cost, and elapsed duration. Restart reconstructs the exact ordered history used by the
retry engine. Prior attempts cannot be updated or deleted.

## Decision rules

- Policy, security, approval, input-contract, and other non-retryable failures stop.
- The task graph's `max_attempts` is an absolute ceiling even when runtime limits are higher.
- The existing retry engine additionally enforces elapsed time, cumulative plus estimated
  next cost, repeated failure fingerprint, and exponential backoff ceilings.
- Transient timeout/environment/provider failures may return the task from `RUNNING` to
  `READY` with `RETRY_SCHEDULED`.
- Retryable implementation, contract-output, or missing-dependency failures return the
  unchanged task to `READY` with `REPAIR_REQUIRED`. External remediation must occur before
  a later tick; the scheduler does not accept a replacement model payload.
- A stop decision durably completes the task as `FAILED` with the original sanitized failure.

## Approval and identity

Sensitive/destructive retries require a new one-use human approval per attempt. Approval
identity includes the attempt number and exact policy action digest. A consumed approval
cannot authorize another handler call.

## Phase AV non-goals

Phase AV does not sleep or run background retry workers, mutate approved inputs, generate
repair code, invoke a reasoning model, estimate provider cost automatically, implement
distributed attempt leases, execute live tools, deploy, publish, or grant production status.
