# Authenticated RAD Agent Application API

Status: Accepted Phase AS boundary | Normative

## Purpose

Phase AS implements the transport-neutral Agent OpenAPI operations over Phases AP, AQ,
and AR. Bearer authentication is supplied through an injected authenticator; callers
cannot construct their own trusted identity context.

## Authorization and requests

Exact scopes are `agent:read`, `agent:write`, `agent:approve`, and
`model-qualifications:read`. Approval additionally requires an authenticated human
principal asserted by the authenticator. Requests, paths, bodies, identifiers, and
headers are bounded and strictly validated. Errors use the public stable envelope and
never expose provider, database, token, or exception text.

## Idempotency

Every mutation requires a 16–128 character idempotency key. Replays are bound to actor,
operation, path, and canonical body digest. A key reused with different input conflicts.
Completed responses are durably stored in SQLite and survive application restart.

## Application flow

Creating a session persists DRAFTING and invokes the qualification-gated AR controller.
Submitting clarification records the AQ lifecycle transition and invokes AR with the
bounded clarification as untrusted context. Candidate reads expose only the latest
validated revision. Approval binds the exact current candidate digest and the
authenticated authorized human principal. No endpoint starts a runtime run.

## Phase AS non-goals

Phase AS does not implement a network server, issue or verify JWT cryptography, manage
users, stream chat, start execution, expose tools, deploy, or grant production status.
