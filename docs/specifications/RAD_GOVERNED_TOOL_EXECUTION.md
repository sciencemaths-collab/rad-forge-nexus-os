# RAD Agent Phase 3A: Governed reference tool execution

Status: implemented reference slice

## Purpose

Phase 3A connects the already-qualified runtime kernel to the bundled local application.
It proves the complete controlled path from an approved candidate to a real workspace side
effect and tamper-evident task evidence without exposing a shell or general-purpose network
client.

## Included capability

The bundled reference runtime registers one tool:

- `workspace.write_artifact`: creates a deterministic, non-executable JSON artifact under
  `WORKSPACE/.rad-agent-artifacts/`.

It is bound to the stages produced by the app-build, research, and data-analysis mode
compilers. This makes the runtime lifecycle usable and testable; it does not claim to
implement domain-specific coding, web research, or statistical computation.

## Governed path

1. A qualified model proposes a candidate specification.
2. A human approves the exact candidate digest.
3. Runtime start recompiles the approved mode graph and binds it to the approved workspace.
4. Each task is evaluated by default-deny policy.
5. `ToolExecutor.preview` validates input and reports effect, input digest, action digest,
   policy decision, reasons, and approval requirement with zero handler invocation.
6. A runtime tick executes at most one ready task through the typed registry.
7. The tool rejects traversal, symlinks, workspace escape, oversized content, conflicting
   overwrite, and non-canonical payloads.
8. Success is recorded in the append-only evidence ledger before task completion.
9. Checkpoints allow runtime recovery without replaying an incompatible graph.

## Availability

Execution is composed only in qualified mode. Development mode remains planning/review only.
The reference capability allowlist is:

- `app_build.planning`
- `research.planning`
- `data_analysis.planning`

A candidate requesting any other capability fails closed during handoff.

## Explicit exclusions

Phase 3A provides no arbitrary shell, subprocess, package installation, remote network
access, email, publishing, deployment, deletion, spending, unrestricted file write, or
production credentials. Acceptance-verifier composition and rich browser execution controls
remain later Phase 3 slices.

## Qualification

Tests must establish:

- dry-run has zero side effects;
- workspace containment and traversal rejection;
- deterministic idempotent replay;
- conflict-safe no-overwrite behavior;
- runtime start and single-tick execution;
- durable task evidence and existing ledger integrity;
- development-mode runtime unavailability;
- complete repository release gates.

Passing these gates qualifies the reference integration, not arbitrary domain tools.
