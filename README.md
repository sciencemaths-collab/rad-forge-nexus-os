# NEXUS Agent / NEXUS OS

**A provider-neutral runtime for governed AI-assisted work.**

NEXUS Agent turns a natural-language objective into a structured, reviewable work
specification. NEXUS OS provides the control layer beneath it: model qualification,
policy evaluation, human approvals, bounded recovery, durable state, typed tools, and
tamper-evident evidence.

The project is designed for work where an AI model should help reason and plan, but
should not be trusted to decide its own permissions or declare its own success.

## Why NEXUS exists

Most agent frameworks begin with a model and a loop: prompt, choose a tool, observe the
result, and repeat. NEXUS separates those responsibilities.

- The **language model** interprets goals and proposes structured plans.
- **NEXUS Agent** manages conversation, clarification, review, and approval.
- **NEXUS OS** governs state transitions, tools, policy, permissions, recovery, and evidence.
- **Deterministic code** validates contracts and performs deterministic computation.
- The **human operator** remains the authority for consequential actions.

Model output is always untrusted input. Availability does not imply qualification, a
generated plan does not imply approval, and task completion does not imply verified success.

## Applications

| Application | Typical use | NEXUS contribution |
|---|---|---|
| Software engineering | Turn requirements into an implementation and verification plan | Contract-first task graphs, approvals, recovery, and evidence |
| Scientific research | Structure questions, sources, calculations, claims, and citations | Provenance, contradiction tracking, deterministic analysis, and review |
| Data analysis | Plan ingestion, quality checks, statistics, charts, and persistence | Reproducible stages, typed computation, and acceptance criteria |
| Internal operations | Coordinate approved tools and repeatable workflows | Policy-scoped actions, durable checkpoints, and audit records |
| Domain-specific agents | Build controlled agents for a laboratory, company, or team | Provider-neutral models plus explicitly registered tools and verifiers |

The included local application supports governed planning and human review. Execution is
enabled by registering real typed tools, policies, capabilities, and acceptance verifiers
for the intended domain.

## How it works

```text
Operator goal
    ↓
NEXUS Agent — clarification and structured proposal
    ↓
Schema validation and exact model qualification
    ↓
Human review and digest-bound approval
    ↓
NEXUS OS — task graph, policy, tools, checkpoints, recovery
    ↓
Acceptance verification and tamper-evident evidence
```

The model proposes. The runtime governs. Tools perform declared operations. Verifiers
evaluate acceptance criteria. Evidence records what actually occurred.

## Core capabilities

- Provider-neutral model and tool interfaces
- Local OpenAI-compatible model support without a mandatory API key
- Adapters for OpenAI/Codex and Anthropic-style providers
- Exact provider, model, and adapter qualification bindings
- Strict validation of model output, API messages, and tool payloads
- Human approvals bound to the exact action digest
- Deny-by-default workspace and network boundaries
- Atomic checkpoints and restart-safe workflow recovery
- Bounded retry and repair by attempt, time, repetition, and cost
- Opaque secret references with scoped resolution and redaction
- Tamper-evident evidence chains and acceptance verification
- Python and TypeScript SDK surfaces
- Local browser interface for login, goal entry, review, and approval

## Local quick start

### Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/)
- A local OpenAI-compatible model server or another configured provider adapter
- A current NEXUS qualification attestation for the exact model binding

Clone and install:

```bash
git clone https://github.com/sciencemaths-collab/rad-forge-nexus-os.git
cd rad-forge-nexus-os
uv sync --all-groups --locked
```

Create a private operator password file:

```bash
install -m 600 /dev/null .nexus-password
printf '%s\n' 'choose-a-long-unique-password' > .nexus-password
```

Configure the model and its attestation:

```bash
export NEXUS_AGENT_MODEL_CONFIG="$PWD/examples/agent-models.local.yaml"
export NEXUS_AGENT_MODEL_ATTESTATION="$PWD/path/to/current-attestation.json"
```

Start the local application:

```bash
uv run nexus-agent-serve \
  --state-dir "$PWD/.nexus-agent" \
  --password-file "$PWD/.nexus-password"
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) on the same computer.

### Usage

1. Log in with the local operator password.
2. Enter a project identifier and describe the objective.
3. Let the qualified model generate a structured candidate specification.
4. Review its objective, constraints, inputs, risks, capabilities, and acceptance criteria.
5. Approve the exact candidate digest or revise the request.

Approval records the reviewed specification. It does not automatically publish, contact
external users, or grant arbitrary tool access.

## Model configuration

NEXUS supports local OpenAI-compatible endpoints such as a compatible Ollama, LM Studio,
or self-hosted inference server. A minimal profile looks like this:

```yaml
schema_version: "1.0"
selected: local_default
profiles:
  local_default:
    type: local_openai
    base_url: http://127.0.0.1:11434/v1
    model: your-qualified-model-id
    adapter_version: "1.0"
    timeout_seconds: 5
```

If the local server requires a credential, use an opaque reference:

```yaml
credential: env:LOCAL_MODEL_KEY
```

NEXUS resolves the value only for the transport call. It does not persist the resolved
credential in configuration, session state, evidence, or browser storage.

Model discovery reports availability only. Before reasoning is allowed, the exact
provider, model, and adapter version must have current evidence permitting the requested
use. See the [local model evaluation runbook](docs/runbooks/LOCAL_MODEL_EVALUATION.md).

## Project configuration

Projects declare their mode, goal, workspace, provider bindings, policy limits, and
acceptance criteria. Versioned examples are available in [`examples/`](examples/).

```yaml
schema_version: "1.0"
project_id: research_example
name: Traceable research workflow
mode: research
goal: Produce an evidence-grounded synthesis of the supplied question.
workspace:
  root: ./workspace
  read_only: false
  network_allowlist: []
providers:
  reasoning:
    adapter: local_openai
    model: your-qualified-model-id
policy:
  max_attempts: 3
  max_elapsed_seconds: 86400
  max_cost_usd: 0
  require_approval: [SENSITIVE, DESTRUCTIVE]
acceptance:
  - id: AC-SOURCES
    description: Every material claim is linked to a recorded source.
    verifier: citation_verification
```

Configuration is schema-validated and canonicalized before use. Literal credentials,
unknown fields, unsafe YAML constructs, invalid endpoints, and incompatible bindings are
rejected.

## Architecture

| Layer | Responsibility |
|---|---|
| Agent application | Conversation, clarification, candidate revisions, and human review |
| Qualification layer | Determines which model uses are supported by verified evidence |
| Runtime kernel | Task graphs, lifecycle transitions, checkpoints, retries, and recovery |
| Policy and approval layer | Evaluates action attributes and enforces exact-scope approval |
| Tool boundary | Validates typed inputs and outputs around every operation |
| Evidence layer | Records outcomes and verifies acceptance without trusting model claims |
| Provider adapters | Isolates models and local inference behind neutral interfaces |

Detailed documents are available in [`docs/architecture/`](docs/architecture/) and
[`docs/specifications/`](docs/specifications/).

## Extending NEXUS

A domain-specific NEXUS application normally supplies:

1. A qualified reasoning-model profile.
2. Typed tool descriptors and handlers.
3. Policy rules for allowed, denied, and approval-gated effects.
4. Capability evidence showing which operations are supported.
5. Acceptance verifiers for the artifacts the workflow claims to produce.
6. An application composition exposing only those registered capabilities.

Core packages do not import vendor SDKs. Provider implementations belong behind adapters,
and deterministic work should remain in deterministic code.

## Security and operating boundary

The included browser application binds only to loopback and is intended for local use.
Do not expose it directly to the internet.

Sensitive, destructive, costly, publishing, external-communication, and production
actions require policy evaluation and human approval. Secrets must remain opaque
references. Never commit password files, resolved credentials, private state directories,
proprietary inputs, or private attestations.

See [`SECURITY.md`](SECURITY.md) for vulnerability reporting and
[`docs/runbooks/STATUS.md`](docs/runbooks/STATUS.md) for precise qualification status.

## SDKs and integration

NEXUS provides Python and TypeScript control surfaces for applications that need to
create and inspect runs, query providers and capabilities, and retrieve or verify
evidence. The embedding application supplies transport and authentication.

- [Python SDK](docs/components/PYTHON_SDK.md)
- [TypeScript SDK](docs/components/TYPESCRIPT_SDK.md)
- [CLI surface](docs/components/CLI_SURFACE.md)
- [Agent API](docs/components/AGENT_APPLICATION_API.md)

## Repository structure

| Path | Purpose |
|---|---|
| `src/nexus_os/` | Runtime kernel, Agent application, adapters, tools, and SDK |
| `schemas/` | Machine-readable validation contracts |
| `contracts/` | REST and MCP interface contracts |
| `examples/` | Model and project configuration examples |
| `docs/architecture/` | Architecture, trust, provider, and security models |
| `docs/specifications/` | Normative behavioral specifications |
| `docs/runbooks/` | Setup, operation, evaluation, and status guidance |
| `docs/evidence/` | Component qualification records |

## Contributing

Contributions should preserve provider neutrality, strict validation, deterministic
governance, deny-by-default access, bounded recovery, and evidence-derived claims. Read
[`CONTRIBUTING.md`](CONTRIBUTING.md) before proposing a change.

## License

RAD Forge / NEXUS OS is available under the [MIT License](LICENSE).
