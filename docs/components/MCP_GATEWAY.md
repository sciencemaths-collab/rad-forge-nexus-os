# Component V: MCP Gateway

Status: TESTED | Boundary contract: 1.0

The gateway provides a transport-neutral JSON-RPC 2.0 dispatcher for `tools/list` and
`tools/call`. It accepts identity, project, trace, and scopes only through an injected
trusted context. Request parameters cannot override those attributes. Envelopes, IDs,
methods, params, and request size are validated before registry or handler access.

Discovery returns the frozen schemas and effect metadata in deterministic order. Calls
flow through Component U for schema validation, policy/approval blocking, timeout,
idempotency, output validation, and safe failure handling. Stable JSON-RPC errors do not
echo payloads, unknown tools, or exception text. A bounded per-actor quota and immutable
metadata-only audit sink record method, tool, identity, trace, outcome, and action digest.

This component is not an HTTP, SSE, WebSocket, or stdio server. Authentication token
verification, authorization administration, durable/distributed rate limits and replay,
durable evidence/audit storage, transport security, backpressure, and multi-process
coordination remain deployment and later integration gates.

