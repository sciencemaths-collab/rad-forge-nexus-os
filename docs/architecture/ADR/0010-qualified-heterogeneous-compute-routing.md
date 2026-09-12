# ADR 0010: Qualified heterogeneous compute routing

Status: accepted

## Decision

RAD treats every compute target as a separate versioned capability, never as an interchangeable
fallback. Phase 7 qualifies the locally available Apple Metal GPU for one bounded workload:
float32 matrix multiplication up to dimension 256 through vQPU 0.6.0, adapter 1.0.0, backend
`apple.metal.mlx`, and MLX 0.32.2. The immutable qualification report must match digest
`sha256:c5a0c47229bf5c9217f00bb5e3d7ef0808e3498c78a1ef454c80795d685c7f68`.

Every execution requires a content-addressed plan, exact human approval, a qualified RAD Node
route, denied network access, zero declared external cost, a real GPU device, no fallback, finite
bounded output, numerical reference verification, output-byte integrity, and a content-addressed
result. Runtime telemetry is kept outside the deterministic result document.

## Consequences

Apple Metal is routable only where the exact runtime and attestation are present. Linux
containers and non-Apple hosts fail closed. HPC, cloud, and physical QPU targets remain visible
as unavailable inventory entries, not executable capabilities. They require target-specific
cost, credential, data-residency, cancellation, numerical, performance, and failure-recovery
qualification on real infrastructure before a future capability version may route to them.
