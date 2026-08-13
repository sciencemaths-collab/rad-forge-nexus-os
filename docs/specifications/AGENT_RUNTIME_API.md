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
