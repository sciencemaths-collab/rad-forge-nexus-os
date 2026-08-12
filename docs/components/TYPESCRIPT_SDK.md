# Component Z: TypeScript SDK

Status: TESTED | Boundary contract: 1.0

The strict ESM `NexusClient` is a typed client for the frozen control API. It provides
run create/get/cancel/resume and provider, capability, and evidence collection methods.
Immutable run values and structured `ApiError` values validate identifiers, lifecycle
states, HTTP status, retryability, request identity, and optional trace propagation.

Mutations require caller-supplied bounded idempotency keys. The client constructs only
versioned relative paths, generates a request UUID when omitted, and rejects malformed
success/error envelopes. Hostile transport exceptions are converted to stable errors
without disclosing their text.

HTTP is an injected `HttpTransport`. The package has no runtime dependencies and does
not discover endpoints or credentials, create authorization headers, weaken TLS, or
select a network library. Concrete transport, authentication configuration, retries,
connection pooling, browser compatibility, and registry publication remain later
integration and release gates.
