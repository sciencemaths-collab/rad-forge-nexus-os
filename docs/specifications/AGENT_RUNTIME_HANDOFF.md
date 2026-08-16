# RAD Agent Runtime Handoff

Status: Accepted Phase AT boundary | Normative

## Purpose

Phase AT deterministically compiles an exactly approved RAD Agent candidate into a
validated governed-runtime mode graph and initializes a durable runtime checkpoint. The handoff
binds session, candidate digest, graph digest, and run identifier without dispatching a
task or granting a reasoning provider execution authority.

## Required gates

- The session is `APPROVED`, or is already `RUNNING` with the same deterministic run.
- The current immutable candidate digest exactly equals the approved digest.
- Every candidate-declared capability appears in the caller-supplied verified capability
  snapshot. Missing capabilities fail closed before checkpoint creation.
- Mode compilation is deterministic code. Candidate/model text cannot add task kinds,
  dependencies, retry policy, effects, or tool calls.
- The runtime checkpoint ends in `READY`; all tasks remain `READY` or `PENDING`.
- The Agent transition appends one `RUN_STARTED` event and binds the run UUID. Repeating
  the same handoff resumes the checkpoint and does not append another event.

## Failure and recovery

The run identifier is UUIDv5-derived from the approved candidate digest. If checkpoint
creation succeeds before the Agent transaction is bound, retrying the same request loads
that compatible checkpoint and completes the binding. A different graph/schema fails the
checkpoint compatibility gate. A stale Agent sequence cannot overwrite session state.

## Phase AT non-goals

Phase AT does not dispatch tasks, invoke tools, resolve secrets, select or call a model,
authenticate identities, infer capability qualification, grant approvals, deploy, publish,
or claim completion. Runtime scheduling and execution remain separately governed.
