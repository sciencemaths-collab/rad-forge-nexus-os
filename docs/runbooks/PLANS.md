# Implementation Plan

The source sequence is the owner-approved A-through-AG order. Each numbered
milestone has its own component loop and cannot advance on a failed gate.

| Milestone | Scope | Exit gate |
|---|---|---|
| 0 Foundation | Specs, architecture, ADRs, contracts, examples | F0 contract validation passes |
| 1 Domain | A-F: config, models, state machine, graph compiler/validator, checkpoints | Unit/contract/security tests and recovery proof |
| 2 Runtime safety | G-O: orchestrator, repair, policy, approval, secrets, sandbox, evidence, qualification, telemetry | Integration/resilience and integrity gates |
| 3 Providers | P-T: adapter SDK, mock, conformance, OpenAI/Codex, Claude | Mock verified; live status explicit |
| 4 Surfaces | U-Z: tools, MCP, API, CLI, Python and TypeScript SDKs | Contract examples execute |
| 5 Modes | AA-AD: deterministic compute and three mode packs | Mode-specific acceptance passes |
| 6 Proof/release | AE-AG: RW-100K, CI/release, clean-room | Release-candidate checklist and evidence |

Work is intentionally serial at dependency boundaries. Independent tests or docs
may be developed concurrently only when they cannot race on the same contracts.
Acceptance changes require an ADR. Git unavailability is an environment blocker,
not permission to omit commit history in the final repository.

