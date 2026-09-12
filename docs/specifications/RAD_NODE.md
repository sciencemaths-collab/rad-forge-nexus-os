# RAD Node 1.0

## Acceptance requirements

1. Node identity is stable, explicit, validated, and cannot be rebound in an existing store.
2. Lifecycle is `STOPPED -> STARTING -> READY -> DRAINING -> STOPPED`; illegal transitions fail.
3. Capability identifier/version bindings are durable and immutable by manifest digest.
4. Discovery requires `node:read`; execution requires `node:execute`.
5. Execution uses Capability Protocol routing and therefore cannot bypass exact qualification,
   expiry, effect, network, timeout, memory, or version constraints.
6. Active executions are bounded. Drain rejects new work and waits for existing work.
7. Every lifecycle and lease transition is append-only, hash-linked, and verified on read.
8. Restart marks incomplete leases `ABANDONED`; it never blindly replays a side effect.
9. Errors are safe and do not serialize payloads, credentials, or implementation objects.
10. Health is deterministic from verified durable state and binding readiness.

The node kernel does not listen on a network interface. Authenticated loopback transport remains
the existing RAD Agent server boundary; remote node networking belongs to federation.
