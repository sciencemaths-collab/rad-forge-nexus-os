# Component U: Typed Tool Registry and Deterministic Execution

Status: TESTED | Boundary contract: 1.0

The registry loads unique, sorted tool descriptors from the frozen MCP tools contract.
Every descriptor declares Draft 2020-12 input/output schemas, effect class, finite
timeout, idempotency behavior, and approval requirement. Handlers are bound separately
so contract discovery never executes code.

The executor canonicalizes and bounds payloads, validates input before policy or handler
execution, evaluates trusted effect attributes through Component I, blocks denial and
approval-required decisions, enforces async timeout, redacts boundary values, validates
output, and returns the exact action digest. Idempotent results are scoped by project,
tool, and key and bound to the input digest; a reused key with changed input fails closed.

The replay cache is currently in memory and does not establish crash-safe idempotency.
Handler sandboxing, durable replay records, approval consumption, MCP framing/auth,
network mediation, telemetry/evidence integration, and distributed concurrency remain
later gateway and application-service gates. This component does not expose a server.

