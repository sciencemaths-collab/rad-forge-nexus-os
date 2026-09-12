# RAD Agent

![RAD Agent applied across warehouse, software, finance, and manufacturing work](docs/assets/rad-agent-use-cases.jpg)

[![CI](https://github.com/sciencemaths-collab/rad-forge-nexus-os/actions/workflows/ci.yml/badge.svg)](https://github.com/sciencemaths-collab/rad-forge-nexus-os/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/sciencemaths-collab/rad-forge-nexus-os?include_prereleases&label=release)](https://github.com/sciencemaths-collab/rad-forge-nexus-os/releases)
[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Governed AI-assisted work, from reasoning to verified results.**

RAD Agent turns a natural-language objective into a structured plan, gives people a clear approval
point, executes only through qualified capabilities, and records evidence of what happened. The
RAD Forge Runtime provides the policy, approval, recovery, tool, and verification controls beneath
that experience.

[Get started](#quick-start) · [See practical applications](docs/RAD_FOR_EVERYONE.md) ·
[Read the user guide](docs/USING_RAD_AGENT.md) · [Review security](SECURITY.md)

> **Current release:** Alpha 4 (`v0.2.0a10`). Suitable for evaluation, local integration, and
> qualified workflows within the documented boundaries. See [release status](docs/runbooks/STATUS.md)
> and [Beta readiness](docs/BETA_READINESS.md) for the evidence behind that designation.

## Why teams use RAD Agent

AI models are useful planners, but reliable work needs more than a prompt-and-tool loop. RAD Agent
separates responsibilities so each part can be inspected and tested:

- A language model interprets the goal and proposes a typed plan.
- The runtime validates the plan and calculates the exact action digest.
- A person reviews and approves consequential work.
- Qualified engines, tools, or sandboxed plugins perform declared operations.
- Independent checks evaluate acceptance criteria and generate tamper-evident evidence.

This design supports provider choice without allowing a model to grant itself permissions or mark
its own output as verified.

## Practical applications

| Team | Example outcome | Current RAD capability |
|---|---|---|
| Software engineering | Build or repair an application from requirements | Structured planning, bounded source editing, governed tests, verification, and evidence |
| Warehouse operations | Allocate available inventory to prioritized orders | Qualified integer allocation, shortage reporting, travel-cost comparison, and evidence export |
| Financial planning | Compare capital allocations within defined risk limits | Qualified recommendation workflow using operator-approved snapshots; no transaction execution |
| Data and operations | Turn repeatable work into reviewable workflows | Typed inputs, policies, approvals, durable checkpoints, and acceptance criteria |
| Manufacturing and infrastructure | Evaluate schedules or compute placements | Extensible capability contracts; each real backend requires its own qualification |
| Evidence review | Organize local sources, claims, calculations, and citations | Provenance-aware planning and deterministic local extraction within approved workspaces |

RAD Agent provides the shared control plane. Domain products and integrations add the appropriate
data contracts, algorithms, policies, and qualified connectors.

## How it works

```text
Goal and approved data
        ↓
Model-generated structured plan
        ↓
Schema, policy, and qualification checks
        ↓
Human review and digest-bound approval
        ↓
Bounded tools, engines, or sandboxed plugins
        ↓
Acceptance verification and evidence
```

## Quick start

The simplest desktop installation uses the signed wheel from the current GitHub release. You need
Python 3.12 or newer, [`pipx`](https://pipx.pypa.io/stable/installation/), GitHub CLI, and a running
local OpenAI-compatible model server such as Ollama or LM Studio.

```bash
mkdir -p rad-download && cd rad-download
gh release download v0.2.0a10 \
  --repo sciencemaths-collab/rad-forge-nexus-os
sha256sum --check SHA256SUMS --ignore-missing
gh attestation verify nexus_os-0.2.0a10-py3-none-any.whl \
  --repo sciencemaths-collab/rad-forge-nexus-os
pipx install ./nexus_os-0.2.0a10-py3-none-any.whl
```

On macOS, use `shasum -a 256 -c SHA256SUMS` for the checksum step.

With the model server running:

```bash
rad setup
rad models list
rad models test
rad doctor
rad serve
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765), sign in with the operator password created
during setup, describe the desired outcome and constraints, review the proposed plan, and approve
only the exact plan you intend to run.

Setup begins in development mode, which supports planning and review. Qualified execution requires
a current attestation for the exact provider, model, adapter version, and intended model use:

```bash
rad setup --mode qualified --attestation /path/to/current-attestation.json --force
```

The [five-minute guide](docs/QUICKSTART_5_MINUTES.md) covers desktop and container installation.
The [complete user guide](docs/USING_RAD_AGENT.md) explains model selection, evaluation,
qualification, authenticated APIs, workflow execution, evidence download, and troubleshooting.

## Container

Versioned Linux images are published for `amd64` and `arm64`. Pin a release tag or immutable
digest; the project does not publish a moving `latest` tag.

```bash
docker pull ghcr.io/sciencemaths-collab/rad-agent:v0.2.0a10
docker run --rm ghcr.io/sciencemaths-collab/rad-agent:v0.2.0a10 --version
```

The browser application and local model endpoint are loopback-only. See the
[container instructions](docs/QUICKSTART_5_MINUTES.md#container-image) for persisted data and host
networking requirements.

## Model providers

| Provider path | Connection support | Execution requirement |
|---|---|---|
| Ollama, LM Studio, or another loopback OpenAI-compatible server | Local discovery and connection testing | Current qualification for the exact provider/model/adapter binding |
| OpenAI | Official-host adapter with opaque credential references | Explicit cloud authorization and current qualification |
| Anthropic | Official-host adapter with opaque credential references | Explicit cloud authorization and current qualification |
| Custom provider | Provider-neutral adapter and conformance contracts | Conformance testing and formal qualification |

Model discovery confirms availability only. It does not qualify a model or authorize tool use.
Credentials are stored as references such as `env:OPENAI_API_KEY`; resolved values are excluded
from configuration, session state, browser storage, and evidence.

## Plugins and domain capabilities

RAD plugin packages use Ed25519 publisher signatures, exact permission review, compatibility
checks, qualification binding, managed installation, audit events, side-by-side versions, and
rollback. Inspect a package before installing it:

```bash
rad plugins inspect ./example.radplug \
  --trust-store ./trusted-publishers.json

rad plugins install ./example.radplug \
  --trust-store ./trusted-publishers.json \
  --qualification ./qualification.json \
  --enable

rad plugins doctor
rad plugins list
```

Qualified zero-permission `wasm-v1` plugins run in a fuel- and memory-bounded Wasmtime sandbox
without host imports. Filesystem, network, secret, and external-action interfaces are not granted
by this runtime. Packages, publisher keys, and qualification evidence currently come directly from
their publishers; a public catalog is planned but not included in this release.

See the [plugin package specification](docs/specifications/RAD_PLUGIN_PACKAGES.md) for the exact
trust and execution contract.

## Current qualified capabilities

- Warehouse allocation: bounded, deterministic single-SKU inventory allocation and evidence.
- Financial decision support: bounded recommendations over operator-supplied snapshots; no trades.
- PathWoven optimization: the five packaged continuous benchmark objectives.
- vQPU local compute: CPU simulation and qualified Apple Metal float32 matrix multiplication on
  the tested hardware/software binding.
- Plugin runtime: signed, qualification-gated, zero-permission WebAssembly operations; no public
  plugin is bundled with this release.

Cloud deployment, WMS/ERP writes, broker transactions, NVIDIA, Slurm, AWS Batch, and physical QPU
execution require separately implemented and qualified adapters. The
[product map](docs/PRODUCT_PLATFORM.md) identifies each present capability and integration boundary.

## Architecture and SDKs

| Layer | Responsibility |
|---|---|
| Agent application | Goal capture, clarification, candidate revisions, review, and approval |
| Qualification | Evidence-based authorization for exact model and capability bindings |
| Runtime | Task graphs, state transitions, checkpoints, retries, and recovery |
| Policy and approval | Effect classification and exact-scope human authorization |
| Tool and plugin boundary | Typed inputs and outputs around bounded operations |
| Evidence | Outcome recording and independent acceptance verification |
| Provider adapters | Model integrations behind provider-neutral contracts |

RAD Agent includes Python and TypeScript SDK surfaces for embedding the control plane. Integrating
applications supply transport, authentication, domain tools, policies, and verifiers.

- [Python SDK](docs/components/PYTHON_SDK.md)
- [TypeScript SDK](docs/components/TYPESCRIPT_SDK.md)
- [Authenticated Agent API](docs/components/AGENT_APPLICATION_API.md)
- [Architecture](docs/architecture/ARCHITECTURE.md)
- [Specifications](docs/specifications/)

## Security

The bundled application binds to loopback and is designed for operation on a trusted local system.
Keep model servers private, use opaque secret references, review exact approvals, and protect local
configuration, state, and evidence directories. See the [Security Policy](SECURITY.md) to report a
vulnerability privately and the [Security Model](docs/architecture/SECURITY_MODEL.md) for design
details.

## Contributing

Contributions are welcome across runtime engineering, adapters, domain contracts, testing,
documentation, and security. Please read the [contribution guide](CONTRIBUTING.md) before opening a
pull request.

## License

RAD Agent and the RAD Forge Runtime are available under the [MIT License](LICENSE).
