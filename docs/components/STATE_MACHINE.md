# Component C: State Machine

Status: TESTED | Lifecycle contract version: 1.0

## Responsibility and boundary

`nexus_os.state_machine` is the deterministic, side-effect-free authority for run
and task lifecycle changes. It exposes explicit transition predicates and guarded
transition operations that return immutable records suitable for later atomic
persistence.

It does not save records, allocate sequence numbers, enforce optimistic locking,
schedule tasks, retry work, evaluate policy, or invoke providers. Component F owns
transactional persistence; later runtime components own orchestration.

## Lifecycle rules

- Runs move through `CREATED → PLANNING → READY → RUNNING` and may pause/resume.
- Cancellation is explicit and durable: active runs enter `CANCELLING` before
  `CANCELLED`; direct `RUNNING → CANCELLED` is illegal.
- Tasks move from pending/readiness/blocking/approval states into execution, then
  one terminal outcome. Terminal states never reopen; repair uses a new attempt in
  the later retry component rather than rewriting history.
- A task transition to `FAILED` requires structured failure metadata. No other
  target accepts failure metadata.
- Every record requires a positive sequence, UTC timestamp, validated trace ID,
  and bounded canonical reason code.
- Self-transitions and all transitions absent from the explicit tables fail closed.

## Qualification limits

This component is TESTED, not production-qualified. It proves transition policy
in memory. The kernel acceptance statement that an illegal transition cannot be
persisted remains pending the transactional checkpoint store and its integration
tests.
