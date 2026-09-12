# Phase 5: RAD Compute Engine

Status: TESTED | Boundary contract: 1.0

vQPU 0.5.0 provides the first qualified compute backend through capability
`rad.compute.local`. RAD exposes only `compute.execute` for the qualified local CPU quantum
simulator. Exact qualification and approval are required, network is denied, and plans/results
are content-addressed. GPU, cloud, HPC, and physical QPU execution remain unqualified and are
therefore not routable through this adapter.
