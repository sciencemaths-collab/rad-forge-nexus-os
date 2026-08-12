# Component T: Claude/Anthropic Adapter

Status: TESTED (FAKE TRANSPORT) | Live status: UNVERIFIED | Boundary contract: 1.0

The adapter maps NEXUS provider tasks to Anthropic Messages through an injected
provider-specific transport. Message identity, type, assistant role, stop reason,
content envelope, and token usage are validated before normalized accepted, started,
completed, or failed events and results enter the provider-neutral core.

Successful stop reasons and incomplete/refusal outcomes are explicitly classified.
The adapter does not advertise resume because the reviewed Messages contract does not
establish the durable response retrieval semantics required by NEXUS. Cancellation is
idempotent after the synchronous message has become terminal; it is not presented as
remote in-flight cancellation.

The core imports no Anthropic SDK and performs no ambient environment lookup. Only an
opaque secret reference is configured; resolved credentials exist inside one transport
call and raw transport exceptions never cross the adapter boundary.

Tests use injected fake transports. They do not prove Anthropic account/model access,
network behavior, streaming compatibility, billing, reliability, tool/workspace
execution, or live cancellation. Explicit isolated live tests are required for
`live_verified`; security, operational, reliability, and release gates are additionally
required for production qualification.

