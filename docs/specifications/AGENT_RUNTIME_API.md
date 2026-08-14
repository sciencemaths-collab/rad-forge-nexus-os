# Authenticated Agent Runtime API

Status: Accepted Phase AX boundary | Normative

## Purpose

Phase AX exposes the Phase AT–AW governed runtime lifecycle through the existing
transport-neutral authenticated Agent application. It adds no alternate execution path:
all work still passes through handoff, policy, approval, typed tools, bounded retry, runtime
evidence, and acceptance verification.

## Operations and scopes

- `POST .../runtime` (`agent:execute`) initializes an exactly approved candidate. The body
  supplies only a bounded workspace root. Required capabilities are derived by an injected
  trusted authorizer; request clients cannot assert them.
- `GET .../runtime` (`agent:read`) returns the durable run/graph/task snapshot.
- `GET .../runtime/preview` (`agent:read`) returns the exact next typed-tool input,
  effect, policy decision, and digests without resolving a handler or changing state.
- `GET .../runtime/evidence` (`agent:read`) returns the ordered, append-only evidence
  records for the exact run after ledger binding and durable runtime recovery. An empty
  ledger is explicitly `EMPTY`; a non-empty response is returned only after full hash-chain
  verification and includes the verified head hash.
- `POST .../runtime/ticks` (`agent:execute`) advances at most one governed task and returns
  `IDLE`, approval, retry, repair, success, or failure state.
- `POST .../runtime/approvals/{approvalId}` (`agent:approve`, authenticated human required)
  decides only an approval belonging to that exact Agent run.
- `POST .../runtime/verify` (`agent:verify`) invokes the Phase AW evidence gate and returns
  the terminal Agent session only after verification.

All mutations require actor/path/operation/body-bound durable idempotency keys. UUIDs,
bodies, scopes, state, and ownership are validated before mutation.

## Durable runtime registry

The API persists the canonical validated graph, run binding, and graph digest. Status and
later mutations reconstruct and revalidate the graph, verify its digest, then resume the
compatible runtime checkpoint. Conflicting session/run/graph reuse fails closed.

## Phase AX non-goals

Phase AX does not open a network socket, implement token cryptography or user management,
connect live tools/providers, auto-run background ticks, alter approved inputs, deploy,
publish, or grant production status.

## Bounded browser automation

The loopback operator UI may advance a run automatically only by issuing the existing
one-task tick request sequentially. It must preview before dispatch, use a fresh idempotency
key for every tick, and cap each automatic request sequence at 100 completed steps. It must
stop before another tick when the operator requests stop or when a tick returns approval,
idle, retry, repair, failure, or any outcome other than task success. Approval remains a
separate authenticated human decision. Browser automation is not a background worker: an
in-flight tick finishes atomically, while closing the UI or stopping prevents the next tick;
durable checkpoints provide later resume.

When automatic verification is enabled, the browser may invoke the existing verification
operation only after the durable runtime reports `SUCCEEDED`. The resulting completion report
must bind the session, run, Agent state, verification outcome, evidence count, verified chain
head, and an explicit qualification label. Local evidence verification must never be labeled
production qualification. Resuming a terminal session reconstructs this report from durable
session and verified evidence reads without repeating the verification mutation.
