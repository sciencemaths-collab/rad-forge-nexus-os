# Component S: OpenAI/Codex Adapter

Status: TESTED (FAKE TRANSPORT) | Live status: UNVERIFIED | Boundary contract: 1.0

The adapter maps NEXUS provider tasks to the OpenAI Responses lifecycle through an
injected provider-specific transport. Requests declare background execution and
`store: false`; normalized accepted, started, completed, failed, and cancelled events
remain provider-neutral. Response identifiers, statuses, token usage, result identity,
cancellation, and retrieval/resume are validated before entering the core boundary.

The core imports no OpenAI SDK and performs no ambient environment lookup. Configuration
accepts an opaque secret reference only. The credential is resolved for one transport
call, closed on every path, and never copied into requests, events, results, errors,
evidence, or Git history. Raw transport exceptions are replaced with safe adapter errors.

Unit, security, integration, and conformance tests use injected fake transports. They
do not prove OpenAI account access, model availability, network behavior, response
compatibility, billing, reliability, workspace/tool execution, or live cancellation.
The adapter remains `unverified` until explicit opt-in live tests pass with isolated
credentials; production qualification additionally requires later security, reliability,
operational, and release gates.

