# Governed Runtime Scheduler

Status: Accepted Phase AU boundary | Normative

## Purpose

Phase AU advances an initialized Phase AT runtime by at most one task per scheduling
tick. It joins deterministic DAG order, durable runtime compare-and-swap, policy,
exact-scope human approval, and typed-tool execution. No model or task prose may choose
the tool, bypass policy, or directly invoke a handler.

## Scheduling contract

- Select the first `READY` task in canonical topological order, or return `IDLE`.
- Resolve task kind to a frozen operator-configured tool binding and require exact task/tool
  effect equality.
- Evaluate a structured action request before leasing or calling the handler.
- On denial, durably fail the task with non-retryable security-policy evidence.
- On required approval, create/reuse a deterministic action-digest-bound approval record,
  transition the task to `WAITING_APPROVAL`, and perform no tool call.
- Resume only with an unexpired `APPROVED` record matching project, run, and action digest.
  Consume that approval atomically at the typed-tool boundary.
- Lease by a runtime checkpoint compare-and-swap transition to `RUNNING`. Execute only
  through `ToolExecutor`, validate output, and durably complete `SUCCEEDED` or `FAILED`.
- One tick handles at most one task. Dependency unlocking remains deterministic runtime code.

## Failure and concurrency

Stale snapshots lose the runtime compare-and-swap and cannot double-dispatch. Approval IDs
are UUIDv5-derived from run, task, and action digest. Mismatched, denied, revoked, expired,
or consumed approvals never reach a handler. Tool exceptions and contract failures are
sanitized and persisted without raw exception text.

## Phase AU non-goals

Phase AU does not implement a background worker pool, distributed leases, retry/repair
integration, streaming, Agent HTTP endpoints, live tools, deployment, publishing, external
communication, or production authorization.
