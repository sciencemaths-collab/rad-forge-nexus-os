# Engineering Status

Last updated: 2026-08-13

Overall state: **TESTED RAD AGENT LOCAL SETUP AND PLANNING/REVIEW BASELINE — NO CAPABILITY IS PRODUCTION READY**

| Area | State | Evidence / blocker |
|---|---|---|
| Repository inventory | VERIFIED | Only the 59-page source PDF was present; no source, manifests, CI, or writable Git repository |
| Specification corpus | VERIFIED | Required corpus created and reviewed against the owner directive and formal PDF |
| Architecture/ADRs | VERIFIED | Initial modular architecture, threat/trust boundaries, and two ADRs created |
| Machine-readable contracts | VERIFIED | Six schemas, OpenAPI, MCP contracts, examples, and semantic graph validation pass |
| BC. RAD local setup | AUTOMATED GATES PASS | `rad setup`, `rad doctor`, `rad serve`, restricted development mode, qualification-preserving mode, compatibility aliases, and all 15 release gates pass |
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
| X. CLI surface | TESTED | 225-test suite, commands, JSON, exit classes, W integration, packaged entry point pass |
| Y. Python SDK | TESTED | 232-test suite, typed client/models/errors, W integration, wheel execution pass |
| Z. TypeScript SDK | TESTED | 235-test Python suite, 6 Node tests, strict declarations, safe transport, package dry run pass |
| AA. Deterministic compute | TESTED | 248-test suite, bounded CSV/schema/statistics/transforms/chart inputs and provenance pass |
| AB. App-build mode | TESTED | 255-test suite, fail-fast engineering DAG, acceptance/retry binding, secret exclusion pass |
| AC. Research mode | TESTED | 262-test suite, provenance/claims/conflicts/citations/reproducibility DAG pass |
| AD. Data-analysis mode | TESTED | 269-test suite, deterministic analysis/chart/explanation/persistence DAG pass |
| Modes | TESTED | AA deterministic compute and all AB-AD mode packs pass component gates |
| AE. RW-100K proof | TESTED | 275-test suite, exact 100K fixture, compute, save/reopen, evidence reports pass |
| AF. CI/release evidence | TESTED | 285-test suite, 15 fail-fast gates, portable dependency audits, secret scan, SBOM/provenance/report bundle pass |
| AG. Clean-room qualification | QUALIFIED | Isolated locked install, all automated gates, independent review, and digest-bound reports pass |
| AH. NEXUS Agent contracts | QUALIFIED (CONTRACT) | Agent/runtime/provider separation, four schemas, lifecycle semantics, separate API contract, 293 tests, all release/clean-room gates pass |
| AI. Local OpenAI-compatible adapter | QUALIFIED (FAKE) | Credential-optional loopback adapter, bounded chat normalization, 303 tests, all release/clean-room gates pass |
| AP. Model qualification registry | QUALIFIED | Exact-binding durable registration, atomic supersession, revocation, read-time integrity checks, and all release/clean-room gates pass |
| AQ. Agent session store | QUALIFIED | Canonical candidate revisions, append-only events, clarification/review/approval lifecycle, and all release/clean-room gates pass |
| AR. Agent reasoning controller | QUALIFIED (FAKE) | Qualification-gated proposal generation, strict JSON/candidate validation, bounded repair, and all release/clean-room gates pass |
| AS. Agent application API | QUALIFIED (FAKE) | Injected bearer authentication, exact scopes, durable replay, full Agent workflow composition, and all release/clean-room gates pass |
| AT. Agent runtime handoff | QUALIFIED | Exact approved-digest and capability gates, deterministic graph/run binding, READY-only checkpoint initialization, and all release/clean-room gates pass |
| AU. Governed scheduler | QUALIFIED | Canonical one-task ticks, policy denial, exact approval parking/consumption, typed-tool dispatch, and all release/clean-room gates pass |
| AV. Scheduler retry/repair | QUALIFIED | Immutable attempt evidence, graph/time/cost/repetition bounds, unchanged-input retry/repair states, and all release/clean-room gates pass |
| AW. Agent completion evidence | QUALIFIED | Digest-bound task outcomes, intact-chain and exact acceptance verification, completion gating, and all release/clean-room gates pass |
| AX. Authenticated runtime API | QUALIFIED (NON-LIVE) | Scoped start/status/tick/approval/verification, server-derived capabilities, durable graph recovery, and all release/clean-room gates pass |
| AY. Local Agent HTTP server | QUALIFIED (LOCAL, NON-LIVE) | Loopback transport, password-derived operator sessions, executable bootstrap, bounded HTTP handling, real-socket security/failure tests, 445-test full suite, and installed-wheel smoke pass |
| AZ. Agent model configuration | QUALIFIED (LOCAL, NON-LIVE) | Local OpenAI-compatible profiles, bounded discovery, opaque credential scoping, exact qualification and health gates, 454-test full suite, release evidence, and installed-wheel smoke pass |
| BA. Local Agent application assembly | QUALIFIED (LOCAL PLANNING) | Default composition root joins auth, qualified model, controller, durable sessions/replay, and server; restart integration, 456-test suite, release evidence, and installed-wheel smoke pass |
| BB. Local Agent UX and public usability | QUALIFIED (LOCAL PLANNING) | Browser login/goal/review/approval, hardened static delivery, accessibility/setup guidance, 457-test suite, release evidence, and installed-wheel asset smoke pass |
| Provider adapters | TESTED (NON-LIVE) | P-T contracts, mock, harness, OpenAI and Anthropic fake transports pass; live remains unverified |
| Release qualification | APPROVED FOR REPOSITORY INTEGRATION | Clean-room and independent review pass; final public-readiness commit still requires current local and hosted verification |

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

## Component X verification

On 2026-08-12 the following passed:

- Full suite: 225 tests
- Run create/get/cancel/resume, provider/capability list, and evidence verify commands
- UUID, project, idempotency-key, and argument validation before client calls
- Canonical JSON stdout, safe JSON stderr, and stable exit-code classes
- Evidence invalidity, authorization, API, validation, and internal error mapping
- Configured-client integration through Component W and exception sanitization
- Ruff, strict mypy, contracts, builds, and offline installed console entry-point smoke

Component X is TESTED, not production-qualified. The reusable CLI requires an injected
control client; the bare installed entry point safely reports `client_not_configured`
until Component Y supplies client/SDK wiring. HTTP transport, authentication discovery,
shell completion, and production distribution remain later gates. Component Y adds the
Python SDK.

## Component Y verification

On 2026-08-12 the following passed:

- Full suite: 232 tests
- Typed run model and structured safe API errors
- Versioned paths, request IDs, trace validation, and idempotency headers
- Run create/get/cancel/resume and provider/capability/evidence collections
- Malformed status/body/trace and hostile transport rejection
- Component W create/get integration and Component X client-port compatibility
- Ruff, strict mypy, contracts, builds, and offline fresh-wheel SDK smoke

Component Y is TESTED, not production-qualified. HTTP transport, endpoint and bearer
configuration, TLS, retry/pooling behavior, and published package compatibility remain
unverified. Component Z adds the TypeScript SDK surface.

## Component Z verification

On 2026-08-12 the following passed:

- Full Python suite: 235 tests; TypeScript/Node suite: 6 tests
- Strict TypeScript compilation with generated declarations and no runtime dependencies
- Run create/get/cancel/resume and provider/capability/evidence collections
- Required mutation idempotency, bounded request IDs, UUID paths, and trace validation
- Immutable response parsing and sanitized API/transport failures
- Ambient credential/endpoint exclusion and npm package-content dry run
- Ruff, strict mypy, contracts, Python builds, and offline installed-wheel smoke

Component Z is TESTED, not production-qualified. Concrete HTTP transport, authentication,
TLS, retry/pooling behavior, browser compatibility, live control-service integration,
registry publication, and downstream consumer compatibility remain unverified. The U-Z
surface milestone is complete at its component-test boundary. Component AA begins the
deterministic compute and mode-pack milestone.

## Component AA verification

On 2026-08-12 the following passed:

- Full suite: 248 tests
- Bounded UTF-8 CSV loading and deterministic schema/type inspection
- Summary counts, nulls, distinct values, minimum, maximum, mean, and median
- Column projection, stable typed sorting, and validated chart input generation
- Engine/version, canonical parameter, explicit seed, and input/output digest provenance
- Immutable post-digest results and safe malformed/hostile-input rejection
- Ruff, strict mypy, contracts, builds, and offline installed-wheel compute smoke

Component AA is TESTED, not production-qualified. Tables remain in memory; out-of-core
execution, date/decimal types, advanced transformations, econometrics, numerical solvers,
chart rendering, large-data benchmarks, and evidence-ledger orchestration remain later
gates. Component AB adds the `app_build` mode pack over kernel contracts.

## Component AB verification

On 2026-08-12 the following passed:

- Full suite: 255 tests
- Specification-through-evidence fail-fast engineering task sequence
- Deterministic version/config-bound graph identity and canonical digest
- Project-bounded creative retries and single-attempt verification gates
- Final evidence-task binding to all declared acceptance identifiers
- Wrong-mode and read-only-workspace rejection before graph execution
- Provider, credential, secret, network, and cost configuration exclusion from tasks
- Frozen graph contract round-trip, Ruff, strict mypy, contracts, builds, and wheel smoke

Component AB is TESTED, not production-qualified. It compiles but does not execute work,
select providers, authorize effects, prove generated software correctness, or qualify a
release. Component AC adds the `research` mode pack with source and claim provenance.

## Component AC verification

On 2026-08-12 the following passed:

- Full suite: 262 tests
- Protocol-through-evidence provenance-first research sequence
- Required source, claim-link, derivation, computation, and reproducibility metadata
- Contradiction retention and unresolved-conflict reporting
- Artifact-grounded numeric synthesis and deterministic citation/value checks
- Explicit non-publication plus provider, credential, and secret exclusion
- Wrong-mode/read-only rejection and final acceptance evidence binding
- Frozen graph round trip, Ruff, strict mypy, contracts, builds, and wheel smoke

Component AC is TESTED, not production-qualified. It compiles but does not acquire sources,
execute computations, classify data, assess scientific quality, authorize egress, or publish.
Component AD adds the `data_analysis` mode pack and closes the modes milestone.

## Component AD verification

On 2026-08-12 the following passed:

- Full suite: 269 tests
- Ingestion-through-evidence deterministic data-analysis sequence
- Dataset shape/digest, schema, quality, statistics, and chart provenance requirements
- Model-generated authoritative numbers explicitly prohibited
- Artifact-ID grounding required for every numeric explanation claim
- Persistence identity and compatible reopen verification gates
- Wrong-mode/read-only rejection plus provider, credential, and secret exclusion
- Frozen graph round trip, Ruff, strict mypy, contracts, builds, and wheel smoke

Component AD is TESTED, not production-qualified. It compiles but does not execute analysis,
render charts, provide a virtual grid, or prove scale/performance. The AA-AD modes milestone
is complete at its component-test boundary. Component AE implements the digest-pinned
RW-100K reference workflow and its integration, persistence, evidence, and benchmark gates.

## Component AE verification

On 2026-08-12 the following passed:

- Full suite: 275 tests
- Deterministic digest-pinned fixture with exactly 100,000 data rows
- Expected four-column schema and deterministic data-quality findings
- Summary statistics, validated digest-linked chart specification, and grounded claims
- Atomic state save, separate-instance reopen, compatibility and digest verification
- Seven-record durable evidence chain plus JSON and Markdown reports
- State mutation and duplicate/replay rejection
- Reproducible environment/timing context without a browser-performance claim
- Ruff, strict mypy, contracts, builds, and installed-wheel workflow smoke

Component AE is TESTED at the runtime-only RW-100K boundary, not production-qualified.
Virtual-grid/browser UI, scrolling, edits, filters, sorting, joins, pivots, chart rendering,
and sub-two-second first usable browser rendering remain unimplemented and unclaimed under
ADR-0002. Component AF adds CI/release-evidence automation and release gates.

## Component AF verification

On 2026-08-12 the following passed:

- Full suite: 281 tests and repository-wide format conformance
- Fail-fast format through build gate execution with first-failure reporting
- Unit, contract, integration, security, provider-conformance, RW-100K, and SDK gates
- Repository secret scan with safe finding paths and no disclosed values
- JSON/Markdown evidence, limitations, checklist, and build-provenance generation
- Lockfile-derived CycloneDX 1.6 SBOM containing 36 Python/npm components
- Least-privilege GitHub workflow and blocking moderate-severity dependency review
- Ruff, strict mypy, contracts, TypeScript tests, builds, and real generator execution

Component AF is TESTED, not independently release-authorized. The hosted qualification job
passed, while GitHub Dependency Review proved unavailable for this private repository without
an Advanced Security entitlement. Blocking portable Python and npm advisory audits now replace
that provider-specific job. The generator intentionally leaves clean-room qualification,
independent review, owner approval, and release-candidate status false; Component AG owns the
first two gates.

## Component AG verification

On 2026-08-12 the following passed:

- Full suite: 285 tests
- Declared-source snapshot with dependency, cache, build, VCS, and prior-evidence exclusion
- Snapshot and automated-evidence SHA-256 binding
- Fresh locked Python and TypeScript installs using disposable per-run caches
- All 15 automated gates, including blocking `pip-audit` and `npm audit`
- Independent placeholder, dynamic-execution, vendor-import, and status-drift review
- Zero independent-review findings and JSON/Markdown qualification reports
- Ruff, repository-wide format conformance, strict mypy, and clean-room execution

Component AG is clean-room QUALIFIED. Its generated technical report deliberately records
human authorization as a separate pending concern rather than manufacturing approval from
automation. On 2026-08-12 the owner explicitly approved the release checklist, public-facing
repository cleanup, and policy-compliant integration of the stacked pull requests after current
verification passes. The authorization does not change repository visibility and does not cover
deployment, package publication, external announcements, or production promotion. No capability
is production ready.

## Component AH verification

On 2026-08-13 the following passed:

- Accepted ADR-0003 and normative NEXUS Agent product/acceptance boundary
- Candidate specification, agent event, agent session, and model qualification
  Draft 2020-12 schemas with valid examples
- Deterministic lifecycle, history, uniqueness, review-readiness, and privileged-use
  qualification semantics
- Separate contract-only Agent OpenAPI boundary; the frozen NEXUS OS Control API and
  implemented dispatcher remain unchanged
- Literal-secret, direct-execution-payload, illegal-transition, state-mismatch,
  duplicate-acceptance, and unsafe-promotion rejection
- Full suite: 293 Python tests and 6 TypeScript tests
- Ruff formatting/lint, strict mypy, schema validation, Python builds, and TypeScript
  package dry-run

Component AH is clean-room QUALIFIED at its contract boundary only. All 15 portable
release gates and the independent review passed with zero findings. NEXUS Agent inference, local
model integration, hardware discovery, controller implementation, durable agent
application services, authentication, streaming, UI, deployment, and live-provider
qualification remain unimplemented and unclaimed. Component AI is the next eligible
component: an OpenAI-compatible local reasoning-provider adapter, after AH integration.

## Component AI verification

On 2026-08-13 the following passed:

- Credential-optional local Chat Completions adapter behind an injected transport
- Explicit loopback-only endpoint validation with port and `/v1` path requirements
- Remote, wildcard, credential-bearing, query-bearing, malformed, and non-HTTP
  endpoint rejection
- Optional opaque credential resolution scoped to each transport call
- Bounded system/prompt and message normalization that excludes arbitrary task
  metadata, tool roles, and secret-like fields
- Strict response identity, assistant content, finish reason, and token usage validation
- Provider-neutral event/result/failure mapping and truthful non-resumable capability
- Existing provider conformance harness pass with a deterministic fake transport
- Focused suite: 10 tests; full suite: 303 Python tests and 6 TypeScript tests
- Ruff formatting/lint, strict mypy, contracts, online/offline Python builds, and
  TypeScript package dry-run

Component AI is clean-room QUALIFIED with an injected fake transport, not live-qualified.
All 15 portable release gates and independent review passed with zero findings. It does
not contain an HTTP client, open a socket, install or download model weights, discover
hardware, stream tokens, establish model quality, or authorize network access. A live
local transport and model-qualification harness remain later components.

## Component AJ verification

On 2026-08-13 the following focused checks passed:

- Complete seven-category reasoning-model evaluation boundary
- Exact evidence-derived Agent proposal-use promotion matrix
- Limited/failing result, missing category, duplicate category, duplicate evidence,
  malformed identifier, invalid validity, and exact-expiry rejection behavior
- Canonical evaluation ordering and SHA-256 qualification digest
- Public model-qualification JSON Schema integration
- Focused suite: 13 tests

Component AJ is clean-room QUALIFIED using synthetic observations. The full 316-test
Python suite, 6-test TypeScript suite, all 15 portable release gates, and independent
review passed with zero findings. It calls no live model, verifies no underlying
benchmark evidence, and grants proposal eligibility rather than execution authority.
Live benchmark cases, controlled evaluator execution, model-specific qualification,
durable revocation, Agent controller integration, owner approval, and production
release remain later work.

## Component AK verification

On 2026-08-13 the following focused checks passed:

- Complete, versioned, seven-category structured-output evaluation corpus
- Provider-neutral sequential execution and bounded per-case timeouts
- Canonical corpus/report digests and raw-output-free observations
- Strict JSON, duplicate-key, rubric, identity, provider, size, timeout, secret, and
  model-authored score/evidence rejection
- PASS/LIMITED/FAIL aggregation and independent evidence binding into Component AJ
- Public evaluation-report Draft 2020-12 schema
- Focused suite: 10 tests

Component AK is clean-room QUALIFIED using an injected fake transport. The full
326-test Python suite, 6-test TypeScript suite, all 15 portable release gates, and
independent review passed with zero findings. It contains no live benchmark corpus,
network client, model installation, evidence persistence, provider comparison, or
production qualification. A controlled live transport and independently maintained
benchmark corpus remain later components.

## Component AL verification

On 2026-08-13 the following focused checks passed:

- Concrete standard-library HTTP/HTTPS transport behind the Phase AI protocol
- Mandatory exact loopback host/port sandbox authorization and localhost pinning
- Bounded canonical requests, responses, timeouts, credentials, and connection closure
- Strict status, content type, UTF-8, JSON object, duplicate-key, and finite-value checks
- Remote/ambiguous endpoint, redirect surface, header injection, oversized payload,
  provider-body leakage, and unauthorized-network rejection
- Full adapter integration using an injected connection with no socket
- Focused suite: 13 tests

Component AL is clean-room QUALIFIED using injected connections. The full 339-test
Python suite, 6-test TypeScript suite, all 15 portable release gates, and independent
review passed with zero findings. Automated tests open no socket and establish no
compatibility claim for Ollama, LM Studio, llama.cpp, or any named model/server
version. Server discovery, process management, weight installation, streaming,
retries, live qualification, owner approval, and production release remain later work.

## Component AM verification

On 2026-08-13 the following focused checks passed:

- Fourteen machine-readable reference cases, with two in each Phase AJ category
- Provider/model-independent exact JSON rubrics spanning software and research work
- Separate trusted SHA-256 anchor and canonical order-independent corpus digest
- Public suite schema plus strict loader and category-depth semantics
- Unknown field, duplicate key, non-finite value, oversized file, secret-like prompt,
  shallow category, changed input, and invalid/mismatched anchor rejection
- Phase AK runner integration with complete passing synthetic rubric responses
- Focused suite: 8 tests

Component AM is clean-room QUALIFIED as a public reference corpus. The full 347-test
Python suite, 6-test TypeScript suite, all 15 portable release gates, and independent
review passed with zero findings. The clean-room snapshot now includes benchmark
sources under a regression contract. No live model was called or scored.
`reference-v1` is public, small, and exact-match, so it is a reproducible baseline
rather than a hidden, statistically complete, or production-grade certification exam.
Controlled variants, rotation, leakage review, expert content review, reliability
analysis, live execution, owner approval, and production release remain later work.

## Component AN verification

On 2026-08-13 the following focused checks passed:

- Installed local-model evaluation command composing Components AL, AI, AM, and AK
- Explicit endpoint/model/corpus/digest/time/run/trace/output/network authorization
- Optional environment credential reference without manifest reference/value leakage
- Canonical endpoint, report, corpus, and manifest digest binding
- Exclusive private atomic output and stable machine-readable summaries/exit classes
- Remote endpoint, missing authorization, invalid time/identity/digest, existing file,
  symlink, unsupported credential backend, and provider exception handling
- Public local-model evaluation manifest schema
- Focused suite: 9 tests

Component AN is clean-room QUALIFIED using injected transports. The full 356-test
Python suite, 6-test TypeScript suite, all 15 portable release gates, and independent
review passed with zero findings. Automated tests open no socket. No live server/model
compatibility, benchmark score, evidence UUID, Agent permission, model qualification,
owner approval, or production release is claimed.

## Component AO verification

On 2026-08-13 the following focused checks passed:

- Canonical Phase AN manifest and report digest verification
- Seven-record category attestation chain with external count and head anchors
- Producer allowlist, BENCHMARK/PASS attestation, run/trace/digest/time/category binding
- Persisted SQLite ledger verification through Phase AJ qualification
- Preservation of observed LIMITED/FAIL outcomes rather than attestation promotion
- Public attested-model-qualification schema and canonical attestation digest
- Manifest/report tamper, wrong chain/head/count, untrusted producer, wrong kind/outcome,
  mismatched digest/result, future time, missing category, and empty trust rejection
- Focused suite: 15 tests

Component AO is clean-room QUALIFIED using synthetic attestations. The full 371-test
Python suite, 6-test TypeScript suite, all 15 portable release gates, and independent
review passed with zero findings. Tests do not assert a real attestor identity, call a
live model, create external evidence, persist qualification, implement revocation,
grant Agent execution authority, or authorize production release.

## Component AP verification

On 2026-08-13 the following focused checks passed:

- Canonical Phase AO and Phase AJ digest re-verification at registration and read
- Durable exact provider/model/adapter qualification records with immutable content
- Atomic replacement that preserves and marks the prior record as superseded
- Irreversible active-record revocation with bounded non-secret audit fields
- Exact-use and exact-time lookup with expiry and qualification limitations enforced
- Restart persistence, duplicate rollback, database-owner tamper detection, and
  append-preserving deletion protection
- Public model-qualification registry-record Draft 2020-12 schema
- Focused suite: 16 tests; full suite: 387 Python tests and 6 TypeScript tests
- Ruff formatting/lint, strict mypy, and contract validation passed

Component AP is clean-room QUALIFIED with synthetic attestations. All 15 portable
release gates and independent review passed with zero findings. It provides proposal-use lookup only;
it does not authenticate operators, choose trusted attestors, distribute revocations,
schedule re-evaluation, grant tool authority, implement the NEXUS Agent controller, or
authorize production release. Owner approval remains separate and no capability is
production ready.

## Component AS verification

On 2026-08-13 the following focused checks passed:

- Bearer token extraction through an injected authenticator; caller cannot supply context
- Exact read, write, approval, and model-qualification scopes
- Authenticated human-principal requirement for candidate approval
- Strict request envelope, path UUID, canonical body, secret, size, and operation checks
- Durable actor/key/operation/path/body-bound idempotent response replay
- Session create through AR, clarification re-entry, candidate/session reads, exact-digest
  approval, and active model-qualification listing
- Stable sanitized 400/401/403/404/409/422/500 error envelopes
- Updated Agent OpenAPI scope and human-principal annotations
- Focused suite: 6 tests; full suite: 418 Python tests and 6 TypeScript tests
- Ruff formatting/lint, strict mypy, and contract validation passed

Component AS is clean-room QUALIFIED using an injected fake authenticator, fake provider,
and synthetic qualification. All 15 portable release gates and independent review passed
with zero findings. It does not implement token cryptography, issue identities, open a socket,
call a live model, stream chat, start a runtime run, expose tools, deploy, or authorize
production release. Owner approval remains separate and no capability is production ready.

## Component AT verification

On 2026-08-13 the following focused checks passed:

- Exact current-candidate and human-approved digest equality before compilation
- Fail-closed verification of every candidate-declared required capability
- Deterministic mode graph and UUIDv5 run identity derived from approved content
- Durable runtime checkpoint initialization ending in `READY` without task dispatch
- Atomic append-only `RUN_STARTED` session transition and exact run binding
- Compatible retry/resume without a duplicate lifecycle event
- Public handoff schema validation and legacy Agent database migration coverage
- Focused Agent/store/handoff suite: 18 tests
- Full suite: 421 Python tests and 6 TypeScript tests
- All 15 portable release gates and isolated clean-room qualification passed

Component AT is clean-room QUALIFIED with synthetic approvals and capability snapshots.
It does not dispatch tasks, invoke tools, authenticate identities, infer qualification,
call a model, deploy, publish, or authorize production release. The Agent now reaches a
governed `READY_NOT_EXECUTED` runtime boundary; controlled scheduling remains next.

## Component AU verification

On 2026-08-13 the following focused checks passed:

- Canonical topological selection and a strict one-task-per-tick execution bound
- Frozen task-kind to typed-tool bindings with exact effect equality
- Structured policy evaluation before lease or handler invocation
- Durable non-retryable task failure on policy denial without a tool call
- Deterministic exact-action approval request and `WAITING_APPROVAL` checkpoint state
- Project/run/action/expiry/status preflight and atomic one-use consumption at dispatch
- Runtime compare-and-swap leasing, dependency unlocking, and sanitized tool failure
- Immutable task-input canonicalization at the typed-tool JSON boundary
- Focused scheduler/runtime/tool/security suite: 15 tests
- Full suite: 425 Python tests and 6 TypeScript tests

Component AU is clean-room QUALIFIED with synthetic policy, approval, and tool handlers.
It does not implement background workers, distributed leases, retry/repair integration,
live tools, external communication, deployment, publishing, or production authorization.

## Component AV verification

On 2026-08-13 the following focused checks passed:

- Append-only contiguous per-run/task attempt evidence with restart recovery
- Sanitized typed-tool failure classification and bounded failure details
- Absolute graph attempt ceiling plus elapsed, cumulative/next-cost, repetition, and
  exponential-backoff limits from the deterministic retry engine
- `RUNNING` to `READY` rescheduling with separately evidenced attempts
- Transient retry scheduling and contract-output repair-required routing
- Approved graph and task input digest preservation across every retry/repair decision
- Non-retryable policy, approval, security, and input-contract failures remain terminal
- New one-use exact-scope approval identity for each sensitive/destructive attempt
- Attempt-row immutability and stored-history tamper detection
- Focused retry/scheduler/runtime/tool/security suite: 31 tests
- Full suite: 431 Python tests and 6 TypeScript tests

Component AV is clean-room QUALIFIED with synthetic failures, costs, elapsed durations,
approvals, and tool handlers. It does not sleep or run background workers, mutate approved
inputs, generate repair code, invoke a model, auto-meter provider cost, execute live tools,
deploy, publish, or authorize production release.

## Component AW verification

On 2026-08-13 the following focused checks passed:

- Deterministic runtime-event evidence bound to task input and validated tool output digests
- Evidence append before final successful task transition and exact idempotent recovery
- Exact Agent session/run/approved-candidate binding before verification
- Successful runtime and every-task-success prerequisites independent of evidence
- Complete passing task evidence set and hash-chain integrity verification
- Exact registered verifier routing for every approved acceptance method
- Environment- and output-digest-bound PASS/FAIL acceptance evidence
- `RUNNING -> VERIFYING -> COMPLETED` only when every approved criterion passes
- Missing task evidence blocks verification; failed acceptance ends the Agent as `FAILED`
- Focused Agent/runtime/evidence suite: 26 tests
- Full suite: 434 Python tests and 6 TypeScript tests

Component AW is clean-room QUALIFIED with synthetic task outputs and deterministic verifier
fixtures. It does not infer truth from model output, discover verifiers, execute live external
tests, generate a UI/report, promote capabilities, deploy, publish, or authorize production.

## Component AX verification

On 2026-08-13 the following focused checks passed:

- Five authenticated runtime operations with exact read/execute/approve/verify scopes
- Durable actor/path/operation/body-bound idempotency on every runtime mutation
- Server-derived capability authorization; request bodies cannot assert qualification
- Approved-candidate handoff and canonical graph/run/digest registry persistence
- Restart-safe graph reconstruction, semantic revalidation, digest check, and checkpoint resume
- One governed scheduler tick per request with approval/retry/repair outcome exposure
- Human-principal and exact Agent-run ownership checks for approval decisions
- Phase AW evidence-gated completion invoked without an alternate execution path
- Strict UUID/body/path validation and sanitized stable application errors
- Focused API/contract/facade suite: 9 tests
- Full suite: 437 Python tests and 6 TypeScript tests

Component AX is clean-room QUALIFIED using injected fake authentication, capability
authorization, tools, and verifiers. It does not open a socket, implement token cryptography,
connect live tools/providers, auto-run workers, deploy, publish, or authorize production.

## Component AQ verification

On 2026-08-13 the following focused checks passed:

- Canonical candidate digest recomputation and exact Phase AH field validation
- Stable candidate identity and monotonically increasing immutable revisions
- Atomic drafting, clarification, specification-ready, review, and approval transitions
- Exact current-candidate digest binding and externally established human principal gate
- Contiguous append-only events, chronology enforcement, and optimistic sequence control
- Restart recovery, stale-writer rollback, stored-event tamper detection, and history
  deletion prevention
- Public candidate and session schema conformance
- Focused suite: 15 tests; full suite: 402 Python tests and 6 TypeScript tests
- Ruff formatting/lint, strict mypy, and contract validation passed

Component AQ is clean-room QUALIFIED using synthetic sessions and reviewer principals.
All 15 portable release gates and independent review passed with zero findings. It does not
authenticate identities, call a model, interpret conversation, start runtime runs,
expose an HTTP/UI service, execute tools, or authorize production release. Owner approval
remains separate and no capability is production ready.

## Component AR verification

On 2026-08-13 the following focused checks passed:

- Exact Phase AP qualification authorization before every candidate or repair call
- Bounded objective-only provider request with a fixed proposal-only system contract
- Controller-owned session/candidate identity, revision, schema version, and digest
- Strict JSON object, duplicate-key, finite-value, exact-field, secret, and size checks
- Phase AQ canonical validation and atomic persistence of ready or clarification candidates
- At most one separately qualified repair call with no invalid-output reflection
- Unqualified model, stale session, malformed output, tool-call field, secret material,
  contradictory readiness, repeated invalid output, and provider failure safe handling
- Focused controller suite: 10 tests; combined Agent suite: 25 tests
- Full suite: 412 Python tests and 6 TypeScript tests
- Ruff formatting/lint, strict mypy, and contract validation passed

Component AR is clean-room QUALIFIED using an injected fake adapter and synthetic
qualification. All 15 portable release gates and independent review passed with zero
findings. It
does not open a socket, establish live-model quality, preserve chat transcripts,
authenticate users, approve candidates, execute tools, start runtime work, expose HTTP/UI,
or authorize production release. Owner approval remains separate and no capability is
production ready.

## RAD Agent Phase 2 model-connection verification

On 2026-08-13 GitHub Actions run 77 passed all 15 portable release gates for the
provider-aware local model-connection slice:

- Explicit Ollama, LM Studio, and generic loopback OpenAI-compatible profile identities
- Automatic conventional-port identification and explicit provider mismatch rejection
- Credential-reference-redacted `rad models list`
- Discovery-only `rad models test` with unavailable-model failure closed
- Exact provider identity included in model qualification authorization
- Unsupported profile types, remote endpoints, and literal credentials remain rejected
- Six focused model-connection test cases, plus the complete Python and TypeScript suites

This slice establishes verified local connection management. It does not perform a live
model inference in CI, qualify a model merely because it is reachable, enable tools, support
remote arbitrary endpoints, or claim direct OpenAI/Anthropic cloud connections. Those
capabilities require their own transport, network-policy, credential, live-test, and
qualification evidence.

## RAD Agent Phase 2B cloud-connection verification

On 2026-08-13 GitHub Actions run 86 passed all 15 portable release gates for direct
official OpenAI and Anthropic model connections:

- Fixed official HTTPS origins and rejection of endpoint overrides
- Bounded, non-redirecting, JSON-only OpenAI Responses and Anthropic Messages transports
- Opaque credential references, header-injection rejection, and sanitized failures
- Authenticated model discovery through the provider-neutral `rad models test` workflow
- Controller-compatible system/user prompts and bounded normalized proposal output
- Normalized input/output token accounting without fabricated price estimates
- Exact provider/model/adapter/use qualification retained
- Credential-free deterministic CI plus separately opt-in live discovery smoke tests
- Full Python and TypeScript suites, type checking, linting, contracts, package build,
  dependency audit, and release evidence passed

This establishes implementation-level cloud connection support. No real provider credential
was available to the default CI run, so live provider availability and model quality remain
unverified until an operator runs the explicit live smoke test and completes exact-model
qualification. Connecting a key does not enable tools or production authorization.

## RAD Agent Phase 3A governed-tool verification

On 2026-08-13 GitHub Actions run 92 passed all 15 portable release gates for the bundled
governed reference execution path:

- Side-effect-free typed-tool preview with input/action digests and policy reasons
- Qualified-mode composition of runtime, scheduler, approval, retry, checkpoint, and evidence
- One default-deny allowlisted `workspace.write_artifact` tool
- Approved-workspace binding in every compiled task input
- Traversal, symlink, workspace escape, oversized content, and conflicting overwrite rejection
- Deterministic idempotent replay
- A real approved runtime start and one-task tick creating a contained artifact
- Evidence append before successful task completion
- Development mode remains without a runtime API
- Full Python/TypeScript, type, lint, contract, security, packaging, audit, and evidence gates

This qualifies only the deterministic reference artifact tool and its local composition. It
does not qualify shell commands, network access, coding engines, research retrieval,
statistical computation, publishing, deployment, deletion, external communication, or
production use. Acceptance-verifier composition and browser execution controls remain open.

## RAD Agent Phase 3B browser-runtime verification

On 2026-08-13 GitHub Actions run 95 passed all 15 portable release gates for the
governed browser operator slice:

- Side-effect-free exact-action preview with typed input, effect, policy decision, and digests
- Authenticated runtime progress and append-only evidence-chain views
- One-step browser execution through the existing governed scheduler only
- Exact-run, single-use approve/deny controls for approval-required actions
- Durable session-ID checkpoint recovery and explicit refresh controls
- Deterministic `runtime_task_evidence` acceptance verification bound to successful task records
- Strict controller enforcement of the supported verifier for newly proposed candidates
- Full Python/TypeScript, type, lint, contract, security, packaging, audit, and evidence gates

This makes the Phase 3A reference runtime operable from the loopback browser without adding
an alternate execution path. It remains limited to deterministic JSON artifacts under the
approved workspace. It does not enable shell commands, arbitrary filesystem access, network
access, publishing, deployment, deletion, external communication, background execution, or
production use.

## RAD Agent Phase 3C bounded-unattended verification

On 2026-08-13 GitHub Actions run 98 passed all 15 portable release gates for bounded
unattended browser execution:

- Sequential automatic progression through the existing preview and one-task tick endpoints
- Fresh mutation idempotency identity and durable checkpoint/evidence refresh for every step
- Operator-configurable 1–100 step bound with a conservative 25-step default
- Stop-after-current-step behavior that preserves atomic in-flight work and prevents the next tick
- Mandatory pause on approval, denial, idle, retry, repair, failure, step bound, or completion
- Resume through the existing durable session and checkpoint controls
- Full Python/TypeScript, type, lint, contract, security, packaging, audit, and evidence gates

This removes repetitive operator clicks for routine qualified work without introducing a
background worker or alternate execution path. Automatic mode remains browser-scoped and
stops when the UI closes. It does not enable shell commands, arbitrary filesystem access,
network access, publishing, deployment, deletion, external communication, unrestricted
autonomy, or production use.

## RAD Agent Phase 3D verified-completion verification

On 2026-08-13 GitHub Actions run 101 passed all 15 portable release gates for the
evidence-bound completion and reporting slice:

- Full hash-chain verification before any non-empty runtime evidence response
- Explicit `EMPTY` versus `VERIFIED` chain status and verified evidence head hash
- Automatic acceptance verification only after durable runtime success
- Task progress plus session/run/outcome/evidence-bound completion reporting
- Explicit `LOCAL_VERIFIED_NOT_PRODUCTION` qualification state and limitations
- Terminal-session report reconstruction from durable reads without replaying verification
- Full Python/TypeScript, type, lint, contract, security, packaging, audit, and evidence gates

This completes the bounded unattended operator flow from exact preview through verified local
completion. It does not transform local evidence into production qualification or add shell,
arbitrary filesystem, network, publishing, deployment, deletion, external communication, or
production capabilities.

## RAD Agent Phase 4A qualified-task-reasoning verification

On 2026-08-13 GitHub Actions run 104 passed all 15 portable release gates for the
proposal-only qualified task-reasoning boundary:

- Exact model-use authorization for task planning and sensitive-action proposals
- Trusted provider/model/adapter/run/task/trace/kind/effect/input/timeout binding
- Exact bounded structured artifact contract with deterministic canonical digest
- One separately qualified repair attempt without invalid-output reflection
- Duplicate, non-finite, unknown, tool-call, secret-like, empty, and oversized rejection
- Secret-like and oversized approved task rejection before provider access
- Ten focused cases; 492-test full Python suite plus all TypeScript and release gates

This is a fake-provider-qualified proposal boundary. It does not compose the reasoner into
runtime execution, register or invoke a tool, write files, read workspace inputs, promote
capabilities, claim task success, publish, deploy, delete, or establish live-model or
production qualification. Governed composition of validated content remains the next phase.

## RAD Agent Phase 4B reasoned-task composition (accepted)

This slice composes the Phase 4A proposal boundary into the governed scheduler while retaining
deterministic control:

- One immutable canonical artifact is bound to the exact run, task, and approved-task digest.
- Missing, drifted, unresolved, spoofed-reserved-field, and conflicting bindings fail closed.
- Resolution adds only the validated artifact and its digest to the original approved input.
- Preview and execution resolve the same payload through the same typed-tool schema boundary.
- Tool selection, effect matching, policy, approval, execution, and evidence remain outside the model.

GitHub Actions run 122 passed all 18 portable release gates on 2026-08-14. The release-evidence
artifact digest is `sha256:c27165410cc94176c4981ec0026c64d0f42f462698e00b024982e1ff54f799ef`.

The slice does not yet expose preparation through HTTP or the browser and does not establish
live-provider or production qualification. Phase 4C will add the authenticated preparation and
review surface without creating an alternate execution path.

## RAD Agent Phase 4C authenticated task preparation (accepted)

This slice exposes the immutable Phase 4B binding through the existing authenticated runtime:

- An idempotent `agent:execute` preparation mutation selects only an exact ready task.
- Existing bindings are recovered without another model call; missing bindings invoke the
  exactly qualified reasoner and persist before preview or execution.
- The browser displays the complete `PROPOSED` artifact and digest before enabling execution.
- Preview and execution remain on the existing policy, approval, typed-tool, and evidence path.

GitHub Actions run 125 passed all 18 portable release gates on 2026-08-14, including Chromium,
Firefox, and the packaged qualified-provider journey. The release-evidence artifact digest is
`sha256:3b3ff9f621a8da21cc1691ad45dc8bae7f521d8ee39f0ed09ea7a2be8b0dc482`.

No live-provider quality or production qualification is claimed.

## RAD Agent Phase 4D graph-wide reasoning evidence (accepted)

This slice closes the graph-level recovery and verification binding:

- A read-only authenticated manifest reports preparation and runtime state for every task in
  deterministic topological order, validating every stored artifact it encounters.
- Task success evidence digests the exact resolved payload used by preview and execution.
- Final completion recomputes every prepared payload and rejects missing, drifted, corrupted,
  or base-input-only task evidence before acceptance verification.
- Existing uncomposed scheduler and verifier behavior remains backward compatible.

GitHub Actions run 129 passed all 18 portable release gates on 2026-08-15, including Chromium,
Firefox, and the complete packaged qualified-provider graph. The release-evidence artifact digest
is `sha256:c82181444460ffed4c2ff7303196056b143e7ff4d0011c73fe21654286501fde`.

The hosted journey also detected and closed canonical serialization of nested immutable task
inputs before acceptance. No live-provider quality or production qualification is claimed.

## RAD Agent Phase 5A operator shell (in progress)

This first browser-upgrade slice makes the supported workflow legible before execution:

- After local authentication, a first-run readiness card reads the authenticated model
  qualification registry and shows either active qualifications or exact `rad setup` and
  `rad doctor` recovery guidance without displaying credentials.
- A persistent lifecycle ribbon labels work as **proposed**, **approved**, **executing**,
  **failed**, or **verified** from durable application state.
- The runtime surface is explicitly an execution timeline, with task states and the exact next
  governed tool call available for inspection.
- Automatic execution exposes a safe pause-after-current-step control; it does not imply
  background cancellation or interrupt an in-flight governed action.

This slice does not yet add in-browser configuration writes, candidate-plan editing, artifact
downloads, or durable cancel semantics. Those remain subsequent Phase 5 work.

## RAD Agent Phase 3E ordinary-user browser acceptance (in progress)

This slice closes browser behavior gaps without adding a new execution path:

- Real Chromium and Firefox interaction tests exercise the served operator interface.
- A final task completed with **Run one governed step** now honors automatic verification.
- A final task completed after an exact human approval now honors automatic verification.
- Failed resumed runs use explicit failure language and never receive the local-success
  qualification label.
- Evidence integrity failures hide completion qualification and surface an `INVALID` chain.
- CI installs both acceptance browsers and records the browser suite as a release-evidence gate.
- A clean-environment gate installs the built wheel outside the source tree and verifies the
  packaged `rad`, `rad setup`, `rad doctor`, and `rad serve` entry points plus browser assets.

The slice remains local-only and is not production qualification. Full qualified provider
composition, interruption recovery, accessibility scanning, and browser trace artifact capture
remain required before Phase 3E can be marked fully accepted.

## RAD Agent Phase 3E recovery and browser-quality acceptance (in progress)

The second Phase 3E slice adds ordinary-user failure and accessibility evidence:

- A connection reset after a durably completed tick reconstructs completion from reads without
  issuing a second tick or replaying the verification mutation.
- Reloading the browser and resuming a terminal session reconstructs the identical report,
  evidence head, and run identity without reverification.
- A real-browser structural accessibility audit requires document language, a main landmark,
  one primary heading, a live status region, labelled form controls, and named buttons.
- Keyboard traversal must reach the password control with a visible focus indicator.
- Failed browser runs retain Playwright traces, screenshots, videos, console context, and server
  test output as a dedicated CI artifact.

This still does not establish full qualified-provider composition, assistive-technology
certification, background execution after browser closure, or production qualification.

## RAD Agent Phase 3E packaged qualified-provider acceptance (accepted)

The final Phase 3E slice exercises the supported application rather than mocked browser APIs:

- Build and install the RAD Agent wheel into an isolated Python environment.
- Start a deterministic loopback OpenAI-compatible provider through the real HTTP transport.
- Register a current, independently evidenced qualification bound to the exact provider, model,
  adapter version, evaluation manifest, and evidence-chain head.
- Start the packaged `rad serve` entry point with owner-only operator credentials.
- Use Chromium and Firefox to log in, create a goal, review and approve the exact candidate,
  select a workspace, initialize the governed runtime, execute the task graph, verify acceptance,
  and display a `VERIFIED` evidence chain with `LOCAL_VERIFIED_NOT_PRODUCTION` qualification.
- Confirm generated artifacts remain confined to the approved `.rad-agent-artifacts` directory.
- Serialize packaged loopback request handling so all composed SQLite stores remain on their
  owning server thread; the full packaged journey detected and closed this composition defect.
- Close every serialized loopback response connection; the browser gate exposed that HTTP/1.1
  keep-alive otherwise lets an idle browser connection starve subsequent requests.
- Encode immutable nested runtime mappings at the HTTP wire boundary; the full automatic journey
  detected the failure when evidence grew beyond the first two task records.
- Separate read-only terminal checkpoint inspection from executable resume so completed runs can
  expose evidence and enter acceptance verification without weakening terminal-state guards.
- Keep the browser verification mutation bodyless, matching the strict authenticated API schema.

This qualifies the deterministic test-provider path and packaged ordinary-user composition. It
does not claim that Ollama, LM Studio, OpenAI, or Anthropic live services passed this run, and it
does not establish background execution or production qualification.

GitHub Actions run 119 passed all 18 automated gates on 2026-08-14. The qualified-browser
gate digest is `sha256:5f421431215ed66ae25231582db1788ab906ee6a49676a90bce6dd8c063fe489`.
The release evidence remains `AUTOMATED_GATES_PASS`, not a production release candidate:
clean-room qualification, independent review, owner approval, and production authorization are
still pending.
