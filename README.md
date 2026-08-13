# RAD Agent

**Reasoning, Action, and Decision for governed AI-assisted work.**

**RAD Agent** stands for **Reasoning, Action, and Decision Agent**. It turns a natural-language objective into a structured, reviewable plan and carries approved work through a governed execution process.

The **RAD Forge Runtime** is the engine beneath the agent. It provides model qualification, policy evaluation, human approvals, bounded recovery, durable state, typed tools, and tamper-evident evidence.

The project is designed for work where an AI model should help reason and plan, but
should not be trusted to decide its own permissions or declare its own success.

## Why RAD Agent exists

Most agent frameworks begin with a model and a loop: prompt, choose a tool, observe the
result, and repeat. RAD Agent separates reasoning, governed decisions, and execution.

- The **language model** interprets goals and proposes structured plans.
- **RAD Agent** manages conversation, clarification, review, and approval.
- The **RAD Forge Runtime** governs state transitions, tools, policy, permissions, recovery, and evidence.
- **Deterministic code** validates contracts and performs deterministic computation.
- The **human operator** remains the authority for consequential actions.

Model output is always untrusted input. Availability does not imply qualification, a
generated plan does not imply approval, and task completion does not imply verified success.

## Applications

| Application | Typical use | RAD Agent contribution |
|---|---|---|
| Software engineering | Turn requirements into an implementation and verification plan | Contract-first task graphs, approvals, recovery, and evidence |
| Scientific research | Structure questions, sources, calculations, claims, and citations | Provenance, contradiction tracking, deterministic analysis, and review |
| Data analysis | Plan ingestion, quality checks, statistics, charts, and persistence | Reproducible stages, typed computation, and acceptance criteria |
| Internal operations | Coordinate approved tools and repeatable workflows | Policy-scoped actions, durable checkpoints, and audit records |
| Domain-specific agents | Build controlled agents for a laboratory, company, or team | Provider-neutral models plus explicitly registered tools and verifiers |

The included RAD Agent application supports governed planning and human review. Execution is
enabled by registering real typed tools, policies, capabilities, and acceptance verifiers
for the intended domain.

## How it works

```text
Operator goal
    ↓
RAD Agent — reasoning, clarification, and structured proposal
    ↓
Schema validation and exact model qualification
    ↓
Human review and digest-bound approval
    ↓
RAD Forge Runtime — governed decisions, actions, checkpoints, recovery
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

## Ways to use RAD Agent

| Path | Best for | What is available now |
|---|---|---|
| Local browser application | Individual operators | Governed planning, candidate review, and exact-digest approval |
| Local authenticated API | Applications on the same computer | Loopback-only access to the planning and review workflow |
| Local OpenAI-compatible model | Private or no-subscription model use | Qualified Ollama-, LM Studio-, or self-hosted compatible endpoints |
| Python or TypeScript integration | Developers embedding the control plane | Typed SDK contracts with application-supplied transport and authentication |
| Custom provider adapter | Teams adding another model backend | Provider-neutral adapter and conformance boundaries |
| Domain-specific agent | Laboratories, engineering teams, and organizations | Runtime components for registered tools, policy, recovery, approvals, and evidence |

The bundled application currently supports local governed planning and human review.
Direct cloud-model setup and domain-specific execution require an explicit qualified
integration; they are not enabled merely by adding an API key.

For the complete walkthrough—including local setup, authenticated API examples, safe
credential references, SDK integration, provider porting, execution requirements, and
troubleshooting—read **[Using RAD Agent](docs/USING_RAD_AGENT.md)**.

## Local quick start

### Requirements

- Python 3.12 or newer
- [`uv`](https://docs.astral.sh/uv/)
- A running OpenAI-compatible model server on the same computer

Clone and install:

```bash
git clone https://github.com/sciencemaths-collab/rad-forge-nexus-os.git
cd rad-forge-nexus-os
uv sync --all-groups --locked
```

Start your local model server, then let RAD Agent detect it and generate private
configuration:

```bash
uv run rad setup
uv run rad doctor
uv run rad serve
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) on the same computer.

The default is explicitly **unqualified development mode**: local planning and human review
only, with no runtime tool execution. Qualified mode requires an independently attested
model binding:

```bash
uv run rad setup --mode qualified --attestation /path/to/current-attestation.json
```

Existing `nexus-*` commands and `NEXUS_AGENT_*` variables remain compatibility aliases.
New integrations should use `rad` and `RAD_AGENT_*`.

### Usage

1. Log in with the local operator password.
2. Enter a project identifier and describe the objective.
3. Let the qualified model generate a structured candidate specification.
4. Review its objective, constraints, inputs, risks, capabilities, and acceptance criteria.
5. Approve the exact candidate digest or revise the request.

Approval records the reviewed specification. It does not automatically publish, contact
external users, or grant arbitrary tool access.

## Model configuration

RAD Agent supports local OpenAI-compatible endpoints such as a compatible Ollama, LM Studio,
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

The runtime resolves the value only for the transport call. It does not persist the resolved
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

## Extending RAD Agent

A domain-specific RAD Agent application normally supplies:

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

RAD Agent provides Python and TypeScript control surfaces for applications that need to
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

RAD Agent and the RAD Forge Runtime are available under the [MIT License](LICENSE).
