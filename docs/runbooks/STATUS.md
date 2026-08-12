# Engineering Status

Last updated: 2026-08-12

Overall state: **MILESTONE 1 IN PROGRESS — NO CAPABILITY IS PRODUCTION READY**

| Area | State | Evidence / blocker |
|---|---|---|
| Repository inventory | VERIFIED | Only the 59-page source PDF was present; no source, manifests, CI, or writable Git repository |
| Specification corpus | VERIFIED | Required corpus created and reviewed against the owner directive and formal PDF |
| Architecture/ADRs | VERIFIED | Initial modular architecture, threat/trust boundaries, and two ADRs created |
| Machine-readable contracts | VERIFIED | Six schemas, OpenAPI, MCP contracts, examples, and semantic graph validation pass |
| A. Configuration loader | TESTED | 20-test full suite, security/failure coverage, canonical digest, and installed-wheel smoke pass |
| B. Core domain models | TESTED | 47-test full suite, immutable JSON boundary, canonical graph digest, and installed-wheel smoke pass |
| C. State machine | TESTED | 63-test full suite, exhaustive lifecycle pair coverage, and installed-wheel smoke pass |
| D. Task graph compiler | TESTED | 73-test full suite, bounded schema compilation, deterministic digest, and installed-wheel smoke pass |
| E. Task graph validator | TESTED | 79-test full suite, dependency/cycle checks, deterministic scheduling levels, and installed-wheel smoke pass |
| F. Durable checkpoint store | TESTED | 85-test full suite, atomic CAS writes, process-kill recovery, compatibility guards, and wheel smoke pass |
| G. Runtime orchestrator | TESTED | 92-test full suite, dependency ordering, durable resume/cancel, stale-snapshot rejection, and wheel smoke pass |
| H. Retry/repair engine | TESTED | 102-test full suite, attempt/time/cost/repetition bounds, deterministic backoff, and wheel smoke pass |
| I. Policy engine | TESTED | 115-test suite, deterministic action digests, denial precedence, and approval classification pass |
| J. Approval store | TESTED | 121-test suite, exact-scope expiry, atomic one-use consumption, restart and race tests pass |
| K. Secrets and redaction | TESTED | 129-test suite, opaque references, scoped resolution, non-serialization, recursive redaction pass |
| L. Workspace sandbox | TESTED | 140-test suite, traversal/symlink escape, scoped writes, environment/network deny-by-default pass |
| M. Evidence ledger | TESTED | 151-test suite, atomic hash-chain append, restart, mutation/deletion/reorder detection pass |
| N. Capability qualification | TESTED | 155-test suite, integrity-bound deterministic promotion and fail-closed rules pass |
| O. Observability | TESTED | 161-test suite, bounded/redacted correlated telemetry and export-failure isolation pass |
| P. Provider adapter SDK | TESTED | 166-test suite, normalized async port/models, redaction, registry, and vendor-neutrality pass |
| Q. Deterministic mock provider | TESTED | 173-test suite, scripted lifecycle/failure/cancel/resume and offline wheel smoke pass |
| R. Provider conformance harness | TESTED | 181-test suite, bounded lifecycle/capability checks, safe failures, stable digest pass |
| S. OpenAI/Codex adapter | TESTED (FAKE) | 188-test suite and fake-transport conformance pass; live provider remains unverified |
| T. Claude/Anthropic adapter | TESTED (FAKE) | 196-test suite and fake-transport conformance pass; live provider remains unverified |
| U. Typed tool registry | TESTED | 203-test suite, schemas, policy gates, timeouts, replay binding, and wheel execution pass |
| V. MCP gateway | TESTED | 211-test suite, strict JSON-RPC, trusted scopes, quota, audit, contract execution pass |
| W. REST control application | TESTED | 218-test suite, all OpenAPI operations, auth scopes, replay binding, wheel smoke pass |
| Modes | UNKNOWN | Correctly not started before deterministic runtime safety |
| Provider adapters | TESTED (NON-LIVE) | P-T contracts, mock, harness, OpenAI and Anthropic fake transports pass; live remains unverified |
| Release qualification | UNKNOWN | Depends on all prior gates |

## Repository state

The local workspace `.git` metadata remains read-only. The owner-authorized GitHub
connector now provides focused remote commits to the private repository. Foundation
commit `2962eefe3ae11707d2c2532578d08d0262aabb93` closed the F0 commit gate.

## Foundation verification

On 2026-08-11 the following passed in the declared `uv` environment:

- `uv run python scripts/validate_contracts.py`
- `uv run pytest -q` — 6 passed
- `uv run ruff check .`
- `uv run mypy src scripts`

The tested contracts are content-addressed by SHA-256 in the command transcript.
The F0 technical checks and focused remote commit pass.

## Component A verification

On 2026-08-12 the following passed:

- Full suite: 20 tests
- Ruff and strict mypy
- Contract/schema validation
- Source distribution and wheel build
- Fresh-environment wheel installation and configuration-load smoke test

Component A is TESTED, not production-qualified. Secret resolution, sandbox path
authorization, and chained evidence remain assigned to later components. The next
component commit was B, core domain models.

## Component B verification

On 2026-08-12 the following passed:

- Full suite: 47 tests
- Ruff and strict mypy
- Contract/schema validation
- Source distribution and wheel build
- Fresh-environment wheel installation and domain import smoke

Component B is TESTED, not production-qualified. It provides immutable shared
values but intentionally does not implement lifecycle transitions or task-graph
semantic validation. The next component is C, the state machine, after Component
B's focused commit.

## Component C verification

On 2026-08-12 the following passed:

- Full suite: 63 tests
- Ruff and strict mypy
- Contract/schema validation
- Source distribution and wheel build
- Fresh-environment installed-wheel state-machine smoke

Component C is TESTED, not production-qualified. It provides deterministic,
side-effect-free lifecycle enforcement and immutable transition records. The
claim that illegal transitions cannot be persisted remains pending Component F's
transactional store integration. The next component is D, task-graph compiler.

## Component D verification

On 2026-08-12 the following passed:

- Full suite: 73 tests
- Ruff and strict mypy
- Contract/schema validation
- Source distribution and wheel build
- Fresh-environment installed-wheel graph compilation

Component D is TESTED, not production-qualified. It compiles bounded untrusted
wire payloads into canonical immutable graphs. Unknown dependencies, cycle
detection, and topological scheduling remain assigned to Component E.

## Component E verification

On 2026-08-12 the following passed:

- Full suite: 79 tests
- Ruff and strict mypy
- Contract/schema validation
- Source distribution and wheel build
- Fresh-environment installed-wheel graph compile/validate smoke
- Iterative validation of a 1,500-task dependency chain

Component E is TESTED, not production-qualified. It proves deterministic graph
semantics in memory. Durable checkpointing and resume begin with Component F.

## Component F verification

On 2026-08-12 the following passed:

- Full suite: 85 tests
- Atomic insert/update and stale-writer rollback
- Forced writer-process termination followed by exact recovery
- Graph/schema resume compatibility rejection
- Secret-reference, non-canonical, and 4 MiB payload rejection
- Ruff, strict mypy, contract/schema validation, builds, and fresh-wheel smoke

Component F is TESTED, not production-qualified. It provides the durable
checkpoint primitive; Component G integrates it with runtime orchestration and
atomic lifecycle progress.

## Component G verification

On 2026-08-12 the following passed:

- Full suite: 92 tests
- Dependency-ordered readiness and terminal run completion
- Durable compatible resume and staged cancellation
- Duplicate/out-of-order task rejection and stale-snapshot CAS protection
- Ruff, strict mypy, contract/schema validation, builds, and fresh-wheel smoke

Component G is TESTED, not production-qualified. It coordinates provider-neutral
runtime state only. Component H adds bounded retry and repair semantics without
rewriting prior attempts.

## Component H verification

On 2026-08-12 the following passed:

- Full suite: 102 tests
- Attempt, elapsed-time, cost, and repeated-failure stopping
- Deterministic capped backoff and retry-versus-repair classification
- Non-retryable security/cancellation handling and hostile numeric rejection
- Ruff, strict mypy, contract/schema validation, builds, and fresh-wheel smoke

Component H is TESTED, not production-qualified. It decides whether another bounded
attempt is eligible but does not authorize the action. Component I adds policy
evaluation before runtime effects.

## Component I verification

On 2026-08-12 the following passed:

- Full suite: 115 tests
- Deterministic allow, deny, and require-approval decisions
- Exact canonical action digest and stable ordered reason codes
- Denial precedence, operation allowlisting, and high-risk effect classification
- Hostile numeric, invalid identifier, oversized metadata, and prompt-injection guards
- Ruff, strict mypy, contract/schema validation, builds, and fresh-wheel smoke

Component I is TESTED, not production-qualified. It classifies and binds actions
but cannot itself authorize an approval-gated effect. Component J adds durable,
exact-digest, expiring, one-use approval records.

## Component J verification

On 2026-08-12 the following passed:

- Full suite: 121 tests
- Durable approval request and explicit approve/deny/revoke transitions
- Exact project/run/action-digest scope and expiration enforcement
- Atomic one-use consumption, replay rejection, and two-consumer race exclusion
- Restart persistence and non-consumption after mismatched authorization
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel smoke

Component J is TESTED, not production-qualified. Authentication and an approval UI
remain integration requirements. Component K adds opaque secret references,
short-lived resolution, and mandatory redaction boundaries.

## Component K verification

On 2026-08-12 the following passed:

- Full suite: 129 tests
- Reference-only parsing and explicit environment/backend resolution
- Scoped close, best-effort buffer clearing, and serialization rejection
- Recursive exact-canary, sensitive-key, reference, and credential-format redaction
- Cycle and nesting-depth attack handling with safe failure messages
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel smoke

Component K is TESTED, not production-qualified. Python cannot guarantee erasure of
all immutable string copies. Backend authentication, subprocess isolation, path and
network restrictions, and provider-specific credential scoping remain later gates.
Component L adds the deny-by-default workspace sandbox.

## Component L verification

On 2026-08-12 the following passed:

- Full suite: 140 tests
- Canonical-root read and explicitly scoped write authorization
- Absolute, traversal, non-normalized, NUL, and symlink-escape rejection
- Non-secret subprocess environment reconstruction from an explicit allowlist
- Deny-by-default exact-host network authorization and port validation
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel smoke

Component L is TESTED, not production-qualified. It authorizes paths, environments,
and hosts but does not itself open files, launch processes, enforce OS resource
limits, or mediate sockets. Descriptor-relative race resistance and deployment
containment remain later security integration gates. Component M adds the durable,
tamper-evident evidence ledger.

## Component M verification

On 2026-08-12 the following passed:

- Full suite: 151 tests
- Canonical SHA-256 record sealing and deterministic schema-aligned export
- Atomic expected-head append, restart persistence, and fork/duplicate rejection
- Mutation, deletion, tail deletion with trusted anchor, reordering, and link detection
- SQLite update/delete prevention through append-only triggers
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel smoke

Component M is TESTED, not production-qualified. A hash chain is tamper-evident,
not tamper-proof: a database owner can replace the database. Trusted anchors,
signatures/WORM storage, and deployment controls remain release hardening. Component
N adds deterministic evidence-to-capability qualification rules.

## Component N verification

On 2026-08-12 the following passed:

- Full suite: 155 tests
- Versioned required-kind and minimum-passing-evidence rules
- Integrity, failure, duplicate-test, and future-evidence refusal
- Deterministic evidence IDs, limitations, and optional expiration
- Automatic promotion capped below production states
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel smoke

Component N is TESTED, not production-qualified. It evaluates immutable input but
does not persist decisions, authenticate release approvers, or grant production
status. Component O adds provider-neutral observability contracts and safe telemetry.

## Component O verification

On 2026-08-12 the following passed:

- Full suite: 161 tests
- Correlated trace, structured-log, and metric event generation
- Bounded scalar attributes and immutable canonical event snapshots
- Exact-canary, prompt, raw payload, user-data, credential, and secret redaction
- Exporter-failure isolation with safe health counters
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel smoke

Component O is TESTED, not production-qualified. The core defines a provider-neutral
export port and bounded test exporter. OpenTelemetry deployment wiring, durable
buffering, sampling, backpressure, alerting, and delivery guarantees remain later
integration/release work. Component P begins the provider adapter SDK.

## Component P verification

On 2026-08-12 the following passed:

- Full suite: 166 tests
- Schema-aligned descriptor and reference-only credential validation
- Immutable normalized tasks, sequenced events, usage, results, and async port
- Recursive provider-boundary redaction and duplicate-safe registry
- Vendor-import exclusion from the core provider SDK
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel smoke

Component P is TESTED, not production-qualified. It defines contracts only and has
not executed any provider. Component Q adds the deterministic mock adapter.

## Component Q verification

On 2026-08-12 the following passed:

- Full suite: 173 tests
- Fixed UTC timestamps and contiguous, repeatable provider event sequences
- Normalized success, injected failure, pending, cancellation, and resume scenarios
- Duplicate/unknown-task, premature-result, and unconfigured-operation rejection
- Provider input/metadata redaction and vendor/randomness import exclusion
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel smoke

Component Q is TESTED at the deterministic mock boundary, not production-qualified.
It performs no provider or network I/O and establishes no live-provider claim.
Component R adds the reusable adapter conformance harness.

## Component R verification

On 2026-08-12 the following passed:

- Full suite: 181 tests
- Typed health/capability discovery and normalized successful lifecycle
- Contiguous event sequencing, task/trace identity, and terminal-result agreement
- Idempotent cancellation, advertised/unsupported resume, and unknown-task rejection
- Bounded timeout, malformed sequence/identity failure, safe details, and stable digest
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel harness smoke

Component R is TESTED at the provider-neutral conformance boundary, not
production-qualified. A passing deterministic suite derives only `mock_verified`.
Live-provider execution, workspace/policy integration, reliability qualification,
and release approval remain later gates. Component S begins the first live adapter
implementation without credentials or a live-verification claim.

## Component S verification

On 2026-08-12 the following passed:

- Full suite: 188 tests
- Responses request mapping with background execution and `store: false`
- Opaque secret references and per-call scoped credential resolution
- Normalized lifecycle, terminal results, token usage, cancellation, and resume
- Malformed identity/status/usage, duplicate task, unknown task, and safe-error checks
- Component R conformance through an injected fake transport
- Vendor SDK/ambient environment exclusion, Ruff, strict mypy, contracts, builds, wheel smoke

Component S is TESTED with deterministic fake transports, not live-verified or
production-qualified. No API key or live request was used. Account/model access,
vendor behavior, network reliability, cost, and real cancellation/resume require
explicit opt-in live qualification. Component T adds the Claude/Anthropic adapter.

## Component T verification

On 2026-08-12 the following passed:

- Full suite: 196 tests
- Anthropic Messages request and strict message identity/type/role validation
- Opaque secret references and per-call scoped credential resolution
- Stop-reason, token usage, success, truncation, and refusal normalization
- Terminal cancellation idempotency and explicit unsupported resume
- Malformed response, duplicate/unknown task, and safe-error checks
- Component R fake-transport conformance, vendor exclusion, typing, contracts, builds, wheel smoke

Component T is TESTED with deterministic fake transports, not live-verified or
production-qualified. No API key or live request was used. Provider milestone P-T is
complete at its non-live component-test boundary. Component U begins the typed tool
registry and deterministic tool execution boundary.

## Component U verification

On 2026-08-12 the following passed:

- Full suite: 203 tests
- Frozen MCP tools contract loading and unique sorted registration
- Draft 2020-12 input/output schema and format validation
- Policy denial and approval-required blocking before handler execution
- Bounded payloads, async timeout, safe handler errors, and output validation
- Project/tool/key-scoped replay and changed-input idempotency rejection
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel execution smoke

Component U is TESTED, not production-qualified. Its replay cache is in memory and does
not yet prove restart-safe or distributed idempotency. MCP protocol framing, gateway
authentication, durable replay, approval consumption, sandbox enforcement, and evidence
integration remain later gates. Component V adds the MCP gateway boundary.

## Component V verification

On 2026-08-12 the following passed:

- Full suite: 211 tests
- Strict bounded JSON-RPC 2.0 envelopes, IDs, methods, and params
- Deterministic `tools/list` and frozen-contract `tools/call` execution
- Trusted actor/project/trace/scopes with request override rejection
- Stable safe errors, per-actor call quota, and metadata-only audit records
- U integration fix for keyed mutation replay versus digest-keyed idempotent reads
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel gateway smoke

Component V is TESTED, not production-qualified. Authentication token verification,
HTTP/stdio hosting, TLS, durable/distributed quota and replay, durable audit/evidence,
and transport backpressure remain unverified. Component W adds the REST/OpenAPI control
application boundary.

## Component W verification

On 2026-08-12 the following passed:

- Full suite: 218 tests
- Dispatcher coverage for every frozen OpenAPI operation ID
- Canonical route/method, path UUID, bounded body, and request ID validation
- Trusted read/write/approval scopes before application-service invocation
- Required mutation idempotency, exact request binding, replay, and conflict rejection
- Stable Error envelopes, safe exception isolation, and trace propagation
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel discovery smoke

Component W is TESTED, not production-qualified. It is an in-process application
boundary, not an HTTP server. Bearer-token verification, TLS, proxy/CORS controls,
durable/distributed replay, repositories, and production middleware remain unverified.
Component X adds the CLI surface over application/client ports.
