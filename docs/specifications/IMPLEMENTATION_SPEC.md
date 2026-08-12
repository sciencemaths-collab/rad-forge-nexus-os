# Implementation Specification

Status: Draft baseline

## Technology baseline

The kernel and control API use Python 3.12 with strict typing and `uv` packaging.
SQLite is the initial transactional checkpoint/evidence backend behind repository
interfaces; PostgreSQL compatibility is a later adapter. The TypeScript SDK is a
generated/thin API client and must not duplicate runtime semantics. ADR-0001
records this choice.

## Module boundaries

- `domain`: immutable IDs, enums, commands, events, results, and validated models.
- `config`: loading, environment overlays, schema validation, and canonicalization.
- `graph`: compilation, dependency validation, cycle detection, and scheduling.
- `runtime`: state transitions and orchestration only; no vendor SDK imports.
- `stores`: transactional state, checkpoint, artifact metadata, and evidence ports.
- `policy`: action classification and decisions; `approval`: durable human gates.
- `secrets`: reference parsing/resolution with non-serializable secret values.
- `sandbox`: workspace/network/process capability enforcement.
- `providers`: adapter protocol, registry, normalized events, conformance kit.
- `tools`: typed deterministic and MCP tool registry/gateway.
- `evidence`: append-only hash chain and verification.
- `qualification`: deterministic evidence-to-capability state rules.
- `observability`: trace/metric/log interfaces and OpenTelemetry implementation.
- `api`, `cli`, and SDKs: public surfaces over application services.
- `modes`: capability packs that compile mode-specific tasks into kernel contracts.

Dependencies point inward toward domain protocols. Vendor libraries may appear
only in adapter packages. Persistence implementations must not leak database types
into domain interfaces.

## Public interfaces

The stable interfaces are the project/config schemas, task/evidence/approval/
capability/provider schemas, AgentAdapter protocol, REST OpenAPI contract, MCP
tools contract, CLI exit behavior, and SDK models generated from contracts.
Breaking changes require versioning, migration guidance, compatibility tests, and
an ADR.

## Execution

Configuration is validated before any side effect. The graph compiler emits a
canonical DAG. The scheduler leases ready tasks; the runtime persists a transition
and checkpoint atomically before dispatch. Provider events are normalized and
validated. Outputs enter verification, then evidence is appended. Repair creates
new bounded attempts; it never rewrites prior evidence. Cancellation is cooperative
first, forceful after a configured grace period, and results in a durable terminal
or resumable state according to task semantics.

## Durability and idempotency

Every run, task attempt, approval, transition, and evidence record has a stable ID.
Mutating API operations accept idempotency keys. Checkpoints include schema
version, graph digest, attempt state, provider cursor where supported, artifact
references, and last committed event. Resume rejects incompatible graph or schema
versions unless an explicit migration succeeds.

## Retry and repair

Failures use the taxonomy `IMPLEMENTATION_BUG`, `CONTRACT_MISMATCH`, `ENVIRONMENT`,
`PROVIDER`, `SECURITY_POLICY`, `MISSING_DEPENDENCY`, `TIMEOUT`, and `CANCELLED`.
Policy defines maximum attempts, elapsed time, cost, and repeated-failure limits.
Security-policy failures and approval denial are not automatically retried.
Provider fallback is allowed only when data policy, capabilities, and task
semantics permit it.

## Configuration

`project.yaml` validates against `schemas/project.schema.json`. Unknown keys are
rejected by default. Secrets use reference syntax only. Defaults are explicit and
canonicalized into a redacted run manifest whose digest is evidence-linked.

## Implementation order and gate

Implementation follows the owner-provided A-through-AG sequence. A component may
advance only after contract, unit, integration, security/failure tests pass and an
evidence record plus status update exists. The working tree must be reviewed and a
focused commit made where the environment permits Git writes.

