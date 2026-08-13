# Product Specification

Status: Accepted baseline

## Purpose

RAD Forge / NEXUS OS turns a user goal, workspace, configuration, policies, and
acceptance criteria into a bounded, inspectable execution whose outputs can be
trusted in proportion to deterministic evidence. It is an autonomous work control
plane, not a model wrapper and not a claim of full autonomy without controls.

## Users

Primary users are software teams, researchers, analysts, platform administrators,
and regulated or security-conscious organizations. Operators configure providers
and policies; reviewers approve effects and inspect evidence; developers extend
adapters and capability packs; auditors verify provenance and qualification.

## Modes

`app_build` compiles product requirements into engineering work and verified
artifacts. `research` manages questions, sources, claims, computation, and
reproducible reports. `data_analysis` manages data ingestion, quality checks,
deterministic computation, visual specifications, grounded explanations, and
persistence. A project declares exactly one primary mode; shared kernel services
must not encode mode-specific behavior.

## Core user journey

The user creates a project configuration containing a goal, mode, workspace,
provider roles, resource limits, policies, secret references, and acceptance
criteria. NEXUS validates it, compiles a task graph, previews effects and required
approvals, executes ready nodes, persists checkpoints and evidence, performs
bounded repair, verifies outputs, and returns artifacts plus limitations.

For the conversational product boundary, NEXUS Agent is the user-facing objective
and specification interface, NEXUS OS is the governing runtime, and reasoning
providers are replaceable untrusted components. The normative separation is defined
in [`NEXUS_AGENT_SPEC.md`](NEXUS_AGENT_SPEC.md) and ADR-0003.

## Non-goals

- Replacing professional judgment or guaranteeing correctness from model output.
- Allowing unrestricted self-modifying or indefinitely running agents.
- Serving as a credential vault; NEXUS resolves references through configured
  secret backends and minimizes secret exposure.
- Automatically performing production, destructive, costly, publishing, or
  communication actions.
- Making all provider capabilities equivalent.
- Claiming production readiness before clean-room qualification.

## Product principles

Specification before implementation; provider neutrality; least privilege;
structured boundaries; durable execution; bounded repair; deterministic compute;
evidence before trust; transparent degradation; portable artifacts; and explicit
human authority over consequential side effects.

## Success criteria

Success is defined by `ACCEPTANCE_SPEC.md`. At minimum, a clean installation must
execute the mock-backed reference workflow, survive restart, enforce approvals and
workspace boundaries, verify the evidence chain, and refuse capability promotion
without sufficient evidence. Live provider qualification is independent and
opt-in.
