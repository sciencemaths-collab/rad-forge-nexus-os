# ADR 0005: RAD Node local execution host

Status: Accepted

## Decision

A RAD Node is a single-host, provider-neutral execution boundary for qualified capabilities. It
has a stable operator-assigned identity, an append-only integrity chain, durable capability
bindings, bounded concurrent leases, explicit lifecycle states, authenticated control scopes,
and crash recovery. The node routes only through Capability Protocol 1.0 and delegates native
tools to their existing governed executor.

Registration records a manifest digest but grants no qualification or execution authority.
Implementations are process-local and must be rebound after restart to the exact persisted
manifest. A restart abandons incomplete leases instead of replaying a possibly completed side
effect. Network listening is not part of the kernel; the existing loopback-authenticated RAD
application is the transport boundary.

Federation, remote enrollment, remote scheduling, package installation, and commercial
entitlements remain later phases.
