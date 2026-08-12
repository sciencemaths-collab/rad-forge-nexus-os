# Protocol Specification

Status: Draft baseline

## Versioning and envelopes

Public APIs are versioned under `/v1`. JSON uses UTF-8, RFC 3339 UTC timestamps,
UUID identifiers, and a standard error envelope: `code`, `message`, `request_id`,
`retryable`, and optional validated `details`. Unknown input fields are rejected
unless a schema explicitly permits extension metadata.

## AgentAdapter

Every provider implements async `healthcheck()`, `capabilities()`, `run(task)`,
`stream_events(task)`, `result(task_id)`, `cancel(task_id)`, and `resume(task_id)`.
Inputs and outputs are normalized domain objects. `resume` must return a typed
unsupported-capability error when unavailable. Cancellation is idempotent.

Provider events contain sequence, time, provider task ID, normalized kind,
redacted payload, and optional trace context. Results declare status, artifacts,
usage, provider metadata, and structured failure. Raw provider payloads are never
trusted or returned across the core boundary without validation and redaction.

## Provider conformance levels

`mock_verified` passes the complete deterministic suite against fixtures.
`live_verified` additionally passes opt-in tests against a named provider/version
in a controlled environment. `production_qualified` requires security review,
reliability evidence, documented limits, operational runbooks, and release approval.

The conformance suite covers initialization, health, capability discovery,
normalized events/results, malformed output, errors, cancellation, optional
resume, timeout, redaction, workspace isolation, and policy enforcement.

## MCP

MCP is a typed tool/service boundary, not the runtime kernel. Each tool declares
JSON Schema input and output, side-effect class, timeout, idempotency behavior,
required permissions, and approval policy. The gateway validates both directions,
sanitizes output, rate-limits calls, propagates trace IDs, and records evidence.

## Control API

The normative surface is `contracts/openapi.yaml`: project creation/read/plan;
run creation/read/cancel/resume/evidence; approval read/decision; provider list;
and capability list. Mutating calls use authentication, authorization, and
idempotency keys. A successful request means accepted state change, not task
completion.

## CLI and SDKs

The CLI is a client of application services and supports machine-readable JSON.
Exit codes distinguish success, validation, policy/approval, execution, integrity,
and internal failures. `nexus evidence verify <run-id>` returns nonzero for gaps,
hash mismatch, malformed records, or an unexpected chain root. Python and
TypeScript SDKs follow OpenAPI semantics and preserve request/trace IDs.

