# Agent Completion and Runtime Evidence

Status: Accepted Phase AW boundary | Normative

## Purpose

Phase AW prevents runtime success or model text from becoming an Agent completion claim.
It binds typed-tool outcomes to the append-only evidence ledger and runs every approved
acceptance criterion through its exact registered deterministic verifier before completion.

## Runtime outcome evidence

- Before a successful task transition is finalized, the scheduler appends a deterministic
  `RUNTIME_EVENT/PASS` record bound to project, run, task, canonical task-input digest,
  validated tool-output digest, actor, producer version, trace, and prior ledger head.
- Evidence identity is UUIDv5-derived from the full binding. Exact retries are idempotent;
  conflicting reuse fails closed.
- Runtime state and evidence are separate durable authorities. Verification requires both,
  so a partial failure can never create a completion claim.

## Completion verification

- The Agent session must be bound to the runtime run and exact approved candidate digest.
- The runtime must be `SUCCEEDED`, and every graph task must be `SUCCEEDED`.
- The ledger hash chain must verify and contain one passing task outcome for every graph task.
- Every approved acceptance ID is routed by its exact `verification_method` to a registered
  verifier. Results bind the criterion, environment identity, and immutable output digest.
- A passing `TEST` evidence record must exist for every approved acceptance ID.
- Only then may `RUNNING -> VERIFYING -> COMPLETED` occur. Any executed verifier failure
  produces durable failing test evidence and `VERIFYING -> FAILED`.

## Recovery and safety

Verification may resume from `VERIFYING`; deterministic evidence appends are idempotent.
Missing task evidence blocks entry into verification. Unknown verifiers, candidate/run
mismatch, broken chains, missing criteria, duplicate/conflicting evidence, and non-successful
runtimes fail closed. Verifier exception text is not accepted as evidence.

## Phase AW non-goals

Phase AW does not infer truth from model output, discover verifiers dynamically, execute
live external tests, generate reports or UI, promote capabilities, deploy, publish, or grant
production status.
