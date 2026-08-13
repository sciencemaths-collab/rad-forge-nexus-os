# Local Agent Application Assembly

Status: frozen for Component BA

## Purpose

BA provides the supported composition root that turns the qualified NEXUS
components into one runnable local planning and human-review application. It
deliberately does not bind invented universal execution tools.

## Contract

- `nexus-agent-serve` uses the built-in local application factory by default.
- Startup requires a validated AZ model profile and a current independently
  attested qualification, supplied by explicit environment path references.
- The composition root creates durable session, qualification, and idempotency
  stores inside the selected private state directory.
- It constructs the loopback sandbox and transport, short-scope secret resolver,
  qualified local adapter, reasoning controller, application service, and AY
  authenticator boundary.
- A user can create a session, receive a strictly validated candidate, clarify,
  inspect, and approve it through the authenticated API. State and mutation
  replay survive application restart.
- Availability, exact model qualification, and attestation integrity are checked
  before the HTTP server begins accepting work.
- Runtime execution remains unavailable unless a later explicit composition
  supplies real typed tools, capability evidence, acceptance verifiers, policy,
  approvals, and the governed runtime facade. No placeholder may claim work.

## Acceptance gates

1. A qualified fake loopback provider exercises the real composition through a
   review-ready session without bypassing controller validation.
2. Restart preserves the session stores and durable idempotent response.
3. Missing configuration, expired/invalid attestation, unavailable provider, or
   unqualified model stops startup.
4. The full release-evidence and installed entry-point gates pass.
