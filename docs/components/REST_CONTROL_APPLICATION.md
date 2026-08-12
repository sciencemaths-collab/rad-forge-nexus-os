# Component W: REST/OpenAPI Control Application

Status: TESTED | Boundary contract: 1.0

The transport-neutral control application represents every operation in the frozen
OpenAPI 3.1 contract. It accepts authenticated actor/scopes/trace only through a trusted
context, matches canonical `/v1` routes and methods, validates path identifiers, bounds
and canonicalizes JSON bodies, requires idempotency keys for mutations, and dispatches
to an injected application-service port.

Mutation replay is scoped to actor and key and bound to operation, path, and canonical
body digest. Changed-input key reuse returns conflict. Read, write, and approval-decision
scopes are checked before service invocation. Responses carry trace identity and stable
Error envelopes; raw application exceptions and request bodies are never echoed.

This component does not open sockets or provide HTTP framework, bearer-token validation,
TLS, CORS, proxy trust, durable/distributed replay, database repositories, rate limits,
or production middleware. The included in-memory service is a deterministic test fixture,
not the runtime application service. Those claims require later integration and release
gates.

