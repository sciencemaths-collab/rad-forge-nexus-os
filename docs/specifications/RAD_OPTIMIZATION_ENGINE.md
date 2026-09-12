# RAD Optimization Engine 1.0

PathWoven-DCGO `0.2.0` is the first implementation, bound through adapter contract `1.0.0` as
`rad.optimization.pathwoven`. RAD accepts only strict data requests for packaged objective IDs;
it does not accept executable objective code. Routing requires exact capability qualification.

The adapter validates engine identity, version, request digest, seed, dimensions, evaluation
budget, finite output, convergence monotonicity, and declared limitations. RAD Node supplies
bounded lifecycle, concurrency, cancellation, evidence, and authority scopes.

Adapter construction requires the complete formal PathWoven qualification report. RAD
canonicalizes it, recomputes its SHA-256 digest, and requires the release-pinned digest
`sha256:71c5046cd1008e9da62065b6d36465d92c5c256004353897432a068d6e4c1c44`, exact engine and
adapter identity, all 50 expected benchmark cases, deterministic replay, passing outcomes, and
bounded evaluation counts. A caller-supplied qualification label alone cannot enable execution.

Qualification is limited to the five built-in benchmark objectives. It is not a global-optimum,
universal-superiority, arbitrary-objective, or production-deployment claim.
