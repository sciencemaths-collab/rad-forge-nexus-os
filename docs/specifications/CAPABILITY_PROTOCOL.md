# RAD Capability Protocol 1.0

## Purpose

The protocol is the common control-plane boundary through which native RAD tools and future
engine operations are registered, discovered, qualified, and selected. It does not replace the
native RAD app-build, research, analysis, planning, approval, editing, test, verification, or
evidence workflows.

## Required behavior

1. A manifest is immutable, canonical JSON with a stable SHA-256 digest.
2. Identifiers and versions are explicit; duplicate identifier/version registration fails.
3. Registration and discovery cause no implementation execution.
4. Discovery exposes no implementation object, credential, or resolved secret.
5. Routing requires an exact identifier and operation and is constrained by allowed effects,
   network posture, timeout, and memory.
6. Capabilities requiring qualification route only with a matching, unexpired `QUALIFIED`
   record. Registration alone grants no authority.
7. Multiple eligible versions without an exact version are rejected as ambiguous.
8. Native tools adapt without weakening their schemas, policy checks, approval requirements,
   timeouts, or idempotency rules.

## Capability kinds

- `NATIVE_TOOL`: an existing governed RAD tool.
- `ENGINE_OPERATION`: compute, optimization, or decision operation.
- `CONNECTOR`: governed external-system integration.
- `HARDWARE_BACKEND`: hardware or quantum execution fabric.
- `DOMAIN_PACK`: versioned domain behavior composed over other capabilities.

## Non-goals for Phase 1

Remote nodes, package installation, federation, engine process supervision, commercial
entitlements, and production promotion are excluded. They build on this contract in later
phases.
