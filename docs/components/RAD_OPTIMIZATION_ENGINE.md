# Phase 3: RAD Optimization Engine

Status: TESTED | Boundary contract: 1.0

The first optimization capability is PathWoven-DCGO 0.2.0 behind adapter 1.0.0 and capability
ID `rad.optimization.pathwoven`. It accepts strict JSON-compatible requests for five built-in
objectives and rejects executable objective code, unbounded parameters, unknown result fields,
non-finite values, identity mismatches, digest mismatches, and non-monotonic convergence.

Two independent gates are required. The adapter must validate the release-pinned, formal
50-case engine qualification artifact before it can be constructed. RAD Node must also receive
an exact, qualified Capability Protocol record before it routes an operation. Execution remains
bounded by the declared 300-second, 4,096 MiB manifest limits and the request evaluation budget.

The deterministic fixture tests prove rejection and routing behavior without claiming execution
of the real engine. The real-engine acceptance installs the PathWoven wheel and executes it
through the adapter and RAD Node. Neither evidence class uses or qualifies an LLM provider.

Qualification covers only the packaged Sphere, Rastrigin, Rosenbrock, Ackley, and Michalewicz
benchmarks. PathWoven is stochastic with deterministic seeded replay; qualification does not
guarantee a global optimum, universal superiority, arbitrary user objectives, or production
fitness for an unstated workload.
