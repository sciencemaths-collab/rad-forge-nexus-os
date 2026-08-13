# RAD Forge / NEXUS OS

RAD Forge / NEXUS OS is a provider-neutral, evidence-driven runtime for autonomous
software engineering, research, and data-analysis workflows. Goals and acceptance
criteria are compiled into bounded task graphs, executed through replaceable provider
adapters and deterministic tools, checkpointed for recovery, evaluated by policy, and
qualified from tamper-evident evidence.

The project treats model output as untrusted input. Schemas, policy decisions, approval
records, deterministic computations, and verified evidence—not provider claims—govern
what the runtime may execute and what it may claim.

## Current maturity

The NEXUS OS implementation sequence and clean-room qualification are complete at the
recorded Component AG boundary. The subsequent NEXUS Agent upgrade now includes the
contract boundary, a fake-transport-tested credential-optional local
OpenAI-compatible adapter, an evidence-derived model-qualification harness, and a
controlled structured-output evaluation runner, and an explicitly authorized loopback
HTTP transport, a digest-anchored 14-case reference reasoning corpus, an explicit
local-model evaluation command, an independently anchored evidence-to-qualification
bridge, and a durable qualification registry with exact-binding lookup and revocation.
The Agent layer now also has durable candidate revisions, append-only session history,
clarification/review transitions, and exact-digest human approval. The current repository
has 402 Python tests plus the TypeScript suite; conversational inference, live attestation,
model installation, operator authentication, and a user interface are not yet implemented.

No capability is currently promoted to production. Live provider access, production
hosting, package-registry publication, and operational deployment remain explicitly
outside the verified boundary. Exact component states and limitations are maintained in
[`docs/runbooks/STATUS.md`](docs/runbooks/STATUS.md).

## Core properties

- Provider-neutral kernel with OpenAI/Codex, Claude/Anthropic, deterministic mock,
  local OpenAI-compatible, and future providers isolated behind adapters
- Schema-validated configuration, task graphs, API messages, tool inputs, and model output
- Deterministic policy evaluation for sensitive, destructive, costly, publishing, and
  external-communication effects
- Scoped, one-use approvals bound to action digests
- Durable atomic checkpoints with restart, resume, cancellation, and compatibility checks
- Workspace and network access denied by default and enabled only through policy scopes
- Opaque secret references with bounded resolution and recursive redaction
- Tamper-evident evidence chains and evidence-derived capability qualification
- Durable exact-model qualification registration, atomic supersession, and revocation
- Durable Agent sessions with immutable candidate revisions and digest-bound approval
- Bounded retry and repair constrained by attempt, elapsed-time, repetition, and cost limits
- Python and TypeScript control clients with caller-injected transports

## Workflow modes

| Mode | Purpose | Verified boundary |
|---|---|---|
| `app_build` | Specification-first software delivery | Deterministic engineering graph compilation and evidence binding |
| `research` | Traceable research synthesis | Source, claim, contradiction, calculation, and citation provenance |
| `data_analysis` | Reproducible analytical work | Deterministic statistics, chart specifications, grounded explanations, and persistence checks |

Every mode uses the same runtime kernel for configuration, task graphs, execution,
policy, approvals, tools, evidence, and qualification.

## Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/) for locked Python environments
- Node.js 24 or newer for the TypeScript SDK checks
- npm for locked TypeScript dependency installation

## Installation for development

```bash
git clone https://github.com/sciencemaths-collab/rad-forge-nexus-os.git
cd rad-forge-nexus-os
uv sync --all-groups --locked
npm ci --prefix sdk/typescript --ignore-scripts
```

Editable source is installed into the locked `uv` environment. Live provider calls do
not run during installation or during the default test suite.

## Validate a project configuration

Start with one of the versioned examples in [`examples/`](examples/). Provider credentials
must be opaque references such as `env:VARIABLE_NAME`, `vault:path`, or
`secret:logical/name`; literal secret values are rejected.

```python
from nexus_os.config import load_project_config

config = load_project_config("examples/project.data-analysis.yaml")
print(config.digest)
print(config.redacted_manifest())
```

The loader applies documented defaults, validates against the packaged JSON Schema,
produces canonical JSON, and computes a stable SHA-256 digest without resolving secrets.

## Run the verification suite

```bash
uv run python scripts/validate_contracts.py
uv run ruff format --check .
uv run ruff check .
uv run mypy src scripts
uv run pytest -q
npm test --prefix sdk/typescript
uv build
```

Generate the full automated evidence bundle with:

```bash
uv run python scripts/release_evidence.py --output artifacts/release-evidence
```

The generator runs the frozen release gates in order, stops at the first failure, scans
for secret material, audits Python and npm dependencies, and emits JSON/Markdown evidence,
CycloneDX SBOM data, build provenance, known limitations, and a release checklist.

Run the isolated qualification path with:

```bash
uv run python scripts/clean_room.py --output artifacts/clean-room
```

The clean-room process creates a declared-source snapshot, excludes caches and build
products, installs locked dependencies with disposable caches, repeats every automated
gate, performs the independent static review, and binds the report to snapshot and
evidence digests.

## CLI and SDK boundaries

The reusable CLI command parser and both SDKs operate through injected control transports.
The installed `nexus` entry point intentionally returns `client_not_configured` until an
application supplies an authenticated control transport; it never guesses an endpoint or
reads ambient credentials.

Supported control operations include:

- create, inspect, cancel, and resume runs
- list providers and qualified capabilities
- retrieve and verify run evidence

See [`docs/components/CLI_SURFACE.md`](docs/components/CLI_SURFACE.md),
[`docs/components/PYTHON_SDK.md`](docs/components/PYTHON_SDK.md), and
[`docs/components/TYPESCRIPT_SDK.md`](docs/components/TYPESCRIPT_SDK.md) for exact contracts.

## Repository map

| Path | Contents |
|---|---|
| `src/nexus_os/` | Provider-neutral runtime kernel, adapters, SDK, and control surfaces |
| `schemas/` | JSON Schema contracts for configuration, graphs, evidence, approvals, and capabilities |
| `contracts/` | OpenAPI and MCP protocol contracts |
| `examples/` | Valid project configurations and task-graph fixtures |
| `tests/` | Unit, contract, integration, security, failure, and benchmark coverage |
| `docs/specifications/` | Normative product, protocol, implementation, and acceptance requirements |
| `docs/architecture/` | Security, trust, provider, observability, and threat models |
| `docs/components/` | Implemented component boundaries and limitations |
| `docs/evidence/` | Component verification records |
| `docs/runbooks/` | Implementation, release, planning, and status procedures |

## Security model

Provider text, tool output, external data, configuration, and API messages cross trust
boundaries and are validated before use. Secrets remain opaque references. High-impact
effects require policy evaluation and exact-scope approval. Workspace and network access
remain denied unless explicitly authorized.

Report suspected vulnerabilities through the private process in
[`SECURITY.md`](SECURITY.md). Avoid public issues for security-sensitive details.

## Support and issue reporting

Use [GitHub Issues](https://github.com/sciencemaths-collab/rad-forge-nexus-os/issues)
for reproducible defects, documentation problems, and narrowly scoped enhancement
proposals. Search existing issues before opening a new report and use the repository's
structured bug-report form when an operation fails.

A useful error report identifies the affected version or commit, operating system,
Python and Node.js versions, installation method, command or API operation, expected
behavior, actual behavior, minimal reproduction steps, and the smallest relevant log
excerpt. Remove credentials, tokens, personal data, proprietary inputs, and resolved
secret values before attaching configuration, logs, screenshots, or evidence artifacts.

General implementation questions may also be raised through GitHub Issues when they are
specific enough to answer and do not disclose sensitive information. Security
vulnerabilities must follow [`SECURITY.md`](SECURITY.md), not a public issue.

## Contributing

Contribution requirements, focused-change expectations, and verification commands are
documented in [`CONTRIBUTING.md`](CONTRIBUTING.md). Specifications and machine-readable
contracts take precedence over implementation convenience.

## License

RAD Forge / NEXUS OS is available under the [MIT License](LICENSE).
