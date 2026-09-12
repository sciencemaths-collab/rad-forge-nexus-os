# ADR 0008: vQPU as the RAD Compute Engine quantum fabric

Status: Accepted

## Decision

RAD generalizes vQPU upward as a compute engine while retaining its quantum-specific fabric.
The first binding exposes only the independently qualified local CPU simulator. Backend identity
is explicit and fallback is prohibited. New CPU, GPU, HPC, cloud, simulator, and QPU backends
must receive separate capability versions, cost/network declarations, and qualification before
RAD can route them.
