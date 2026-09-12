# ADR 0004: Versioned capability protocol

Status: Accepted

## Context

RAD already has governed native tools and evidence-derived capability qualification. Future
compute, optimization, decision, connector, and hardware implementations need to participate
in the same runtime without becoming agents or bypassing RAD's policy, approval, evidence, and
verification boundaries.

## Decision

Introduce a provider-neutral Capability Protocol 1.0. A capability manifest declares a stable
identifier and version, implementation kind, operations, effects, determinism, network posture,
approval posture, and bounded resources. Registration is immutable per identifier/version and
content-addressed. Discovery returns only public manifest and qualification data; it never
returns or invokes an implementation.

Routing is deterministic and fail-closed. It requires an exact capability identifier and
operation, rejects unqualified or expired implementations, enforces effect and resource limits,
and rejects ambiguous matches unless the caller pins a version. Qualification remains derived
from the existing integrity-verified evidence rules. Registration does not confer qualification.

Existing `ToolDescriptor` instances enter the protocol through an adapter and retain their
current executor, policy, approval, schema-validation, timeout, and evidence behavior.

## Consequences

- Engines are governed callable implementations, not autonomous policy authorities.
- Installing or registering an implementation never authorizes its execution.
- Silent version selection is prohibited when multiple eligible versions exist.
- The existing qualification-record schema and `/v1/capabilities` response remain compatible.
- Node federation, remote installation, engine lifecycle, and commercial entitlements are later
  phases and are not implied by this decision.
