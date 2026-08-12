# Component Y: Python SDK

Status: TESTED | Boundary contract: 1.0

The async `NexusClient` is a thin typed client for the control API. It provides run
create/get/cancel/resume and provider, capability, and evidence collection methods, plus
a generic request method compatible with the CLI client port. Immutable `Run` and
structured `ApiError` models validate identifiers, states, status, retryability, request
identity, and trace propagation.

Mutations require caller-supplied bounded idempotency keys. The client builds versioned
paths and headers, generates a request UUID when omitted, rejects malformed success and
error envelopes, and sanitizes transport failures. It does not expose raw bodies or
transport exception text in exception strings.

HTTP is represented by an injected async transport protocol. The SDK does not select an
endpoint, read bearer credentials, weaken TLS, or import a vendor HTTP library. Concrete
network transport, authentication configuration, retries, connection pooling, and
production distribution remain later integration/release gates.

