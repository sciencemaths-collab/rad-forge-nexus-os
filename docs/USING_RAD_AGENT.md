# Using RAD Agent

RAD Agent is an alpha, provider-neutral system for **Reasoning, Action, and Decision**
under explicit policy, approval, and evidence controls. This guide separates what can be
used today from extension points that require integration work.

## Choose how you want to use it

| Use path | Intended user | Current status |
|---|---|---|
| Local browser application | An operator who wants governed planning and review | Supported on one computer with a qualified local model |
| Local authenticated HTTP API | A local application integrating the planning/review flow | Supported on loopback only |
| Local OpenAI-compatible model | Users of a self-hosted endpoint such as Ollama, LM Studio, or another compatible server | Supported when the exact model binding has current qualification evidence |
| Key-protected loopback model server | A local gateway or server that requires a credential | Supported through an opaque environment-variable reference |
| Direct cloud-model API | Developers connecting directly to a hosted provider | Adapter foundations exist; the bundled local application does not currently enable direct cloud endpoints |
| Python or TypeScript SDK | Developers embedding the control interface | Typed SDK surfaces exist; the embedding application must supply transport and authentication |
| Domain-specific executing agent | A laboratory, engineering team, or company registering real tools | Runtime components exist; the deployer must provide qualified tools, policies, capabilities, approvals, and acceptance verifiers |
| MCP integration | A host exposing registered RAD Agent tools through MCP | Gateway contract exists; production composition and qualification remain the deployer's responsibility |

The included local application **plans, presents a structured candidate, and records human
approval**. It does not automatically edit files, publish content, contact people, or run
arbitrary tools.

## Tutorial: run the local browser application

### 1. Install the project

Requirements:

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/)
- A separately running OpenAI-compatible model endpoint bound to loopback
- Current qualification evidence for the exact provider, model, adapter version, and uses

```bash
git clone https://github.com/sciencemaths-collab/rad-forge-nexus-os.git
cd rad-forge-nexus-os
uv sync --all-groups --locked
```

### 2. Start a compatible local model server

Start the model server according to its own documentation. RAD Agent expects an
OpenAI-compatible `/v1` endpoint on the same computer. Common loopback addresses include:

- Ollama-compatible endpoint: `http://127.0.0.1:11434/v1`
- LM Studio-compatible endpoint: use the loopback port displayed by LM Studio
- Another self-hosted server: use its explicit loopback `/v1` address

Do not bind an unauthenticated model server to a public network.

Confirm the exact model identifier reported by the server. Availability alone does not
qualify the model for RAD Agent reasoning.

### 3. Run guided setup

With the model server running, use the supported setup command:

```bash
uv run rad setup
```

RAD Agent probes fixed loopback ports used by common OpenAI-compatible local servers,
discovers reported model identifiers, asks you to create the local operator password, and
writes owner-only settings. It does not download a model, contact a cloud service, or invent
qualification evidence.

If more than one endpoint or model is available, select it explicitly:

```bash
uv run rad setup \
  --base-url http://127.0.0.1:11434/v1 \
  --model YOUR_EXACT_MODEL_ID
```

Setup rejects remote URLs, embedded credentials, ambiguous selection, unsafe credential
values, and incompatible endpoints. A key-protected loopback gateway may use an opaque
reference such as `--credential-ref env:LOCAL_MODEL_KEY`.

### 4. Check readiness

```bash
uv run rad doctor
```

Doctor checks the generated settings, private password permissions, model configuration,
endpoint availability, selected model, and qualification requirement. It does not invoke
model inference.

### 5. Choose the operating mode

The default is **development mode**. It is deliberately marked unqualified and supports
local candidate planning, bounded proposal repair, human review, and approval recording
only. It has no runtime tools and cannot authorize tool selection or sensitive actions.

For qualified mode, supply a current independently verified attestation during setup:

```bash
uv run rad setup \
  --mode qualified \
  --attestation /path/to/current-attestation.json \
  --force
```

The attestation must match the exact `local_openai` provider, model identifier, adapter
version, permitted uses, and current time. A public evaluation result alone is not an
attestation. See the [local model evaluation runbook](runbooks/LOCAL_MODEL_EVALUATION.md)
and [attestation schema](../schemas/attested-model-qualification.schema.json).

### 6. Start RAD Agent

```bash
uv run rad serve
```

Development mode prints a visible unqualified-mode warning at startup. The server remains
bound to loopback. Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/).

Preferred environment names use `RAD_AGENT_*`. Existing `NEXUS_AGENT_*` variables and
`nexus-*` commands remain temporary compatibility aliases.

### 7. Complete the first planning workflow

1. Log in with the operator password.
2. Enter a project identifier using lowercase letters, numbers, underscores, or hyphens.
3. Describe the desired outcome, constraints, inputs, risks, and acceptance conditions.
4. Generate the candidate specification.
5. Review every field and its digest.
6. Approve only the exact candidate you reviewed.

Approval records the reviewed specification. The included screen does not execute or
publish the work.

## Use the authenticated local HTTP API

The local HTTP server is useful for another application running on the same computer.
It is not a public multi-user API and must not be exposed directly to the internet.

### Health check

```bash
curl http://127.0.0.1:8765/healthz
```

### Log in

```bash
curl -X POST http://127.0.0.1:8765/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"password":"YOUR_OPERATOR_PASSWORD"}'
```

Copy the returned `access_token` and use it as a bearer token.

### Create a planning session

```bash
curl -X POST http://127.0.0.1:8765/v1/agent/sessions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Idempotency-Key: create-session-00000001' \
  -d '{
    "project_id":"research_review",
    "objective":"Prepare a traceable plan to review the supplied evidence and define acceptance criteria."
  }'
```

Use the returned `session_id` to inspect its generated candidate:

```bash
curl http://127.0.0.1:8765/v1/agent/sessions/YOUR_SESSION_ID/candidate \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

To approve, send the exact `candidate_digest` returned by that request:

```bash
curl -X POST http://127.0.0.1:8765/v1/agent/sessions/YOUR_SESSION_ID/approve \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer YOUR_ACCESS_TOKEN' \
  -H 'Idempotency-Key: approve-session-00000001' \
  -d '{"candidate_digest":"YOUR_EXACT_CANDIDATE_DIGEST"}'
```

Bearer tokens are short-lived, held only in memory, and invalidated when the server
restarts. Mutating requests require a unique idempotency key.

## Use a model server that requires an API key

A credential is optional for a loopback OpenAI-compatible endpoint. Keep the value in an
operator-controlled environment variable:

```bash
export LOCAL_MODEL_KEY='replace-with-the-real-secret'
```

Reference it in the model profile without copying the secret into YAML:

```yaml
credential: env:LOCAL_MODEL_KEY
```

The resolver reveals the value only within the transport call. Do not put literal keys in
configuration, source code, shell history, browser storage, evidence, or committed files.

### What about OpenAI, Anthropic, or another cloud API?

The repository contains provider-neutral adapter foundations and reviewed fake-transport
implementations for OpenAI/Codex and Anthropic. Their live cloud behavior remains
unverified, and the bundled local browser composition rejects non-loopback model URLs.
Therefore, direct cloud API setup is **not yet a supported end-user path**.

A safe cloud deployment requires a concrete authenticated transport, live conformance
testing, exact model qualification, cost and data-policy controls, and an application
composition that explicitly selects that adapter. Do not work around the loopback
restriction by changing a URL check and calling the result production-ready.

## Embed RAD Agent with the SDKs

The repository provides typed Python and TypeScript client surfaces for run lifecycle,
providers, capabilities, approvals, and evidence.

- [Python SDK contract](components/PYTHON_SDK.md)
- [TypeScript SDK contract](components/TYPESCRIPT_SDK.md)
- [Control API contract](../contracts/openapi.yaml)

These are integration surfaces, not turnkey hosted clients. The embedding application must
provide:

1. A concrete HTTP transport.
2. Endpoint selection.
3. Authentication and secret handling.
4. TLS for any non-local deployment.
5. Retry, timeout, and connection-pooling policy.
6. A qualified RAD Agent server composition.

The packages are not documented as generally published PyPI or npm releases. Until a
release process states otherwise, integrate from a reviewed source revision and preserve
the frozen contracts.

## Port a new model provider

A provider adapter translates provider-specific requests and responses into RAD Agent's
stable internal contracts. It must not leak vendor types into the runtime.

### Required integration sequence

1. Implement the stable asynchronous `AgentAdapter` boundary.
2. Put vendor networking behind an injected transport; do not import a vendor SDK into the core.
3. Use opaque secret references and scope resolution to a single transport call.
4. Normalize lifecycle events, results, failures, usage, cancellation, and supported capabilities.
5. Strictly validate all provider output before it reaches planning or execution.
6. Register the adapter explicitly; do not use ambient provider discovery.
7. Run the provider conformance harness with deterministic fake transport.
8. Add opt-in live tests for the exact provider and model.
9. Record capability and model qualification evidence.
10. Compose the adapter into an application with explicit policy, cost, network, and data boundaries.

Start with:

- [Provider architecture](architecture/PROVIDER_MODEL.md)
- [Provider adapter SDK](components/PROVIDER_ADAPTER_SDK.md)
- [Provider conformance harness](components/PROVIDER_CONFORMANCE_HARNESS.md)
- [OpenAI/Codex adapter](components/OPENAI_CODEX_ADAPTER.md)
- [Anthropic adapter](components/CLAUDE_ANTHROPIC_ADAPTER.md)

Passing fake-transport tests does not establish live account access, model quality,
reliability, billing correctness, or production readiness.

## Prepare local research sources

For a candidate whose approved mode is `research`, create a `research-sources` directory in
the workspace selected in the browser. Add bounded UTF-8 Markdown or text sources and declare
each one in `research-sources/manifest.json`:

```json
{
  "schema_version": "1.0",
  "sources": [
    {
      "path": "source-note.md",
      "locator": "local:research/source-note",
      "retrieved_at": "2026-08-16T00:00:00Z",
      "license_access": "Operator-supplied copy used for local analysis"
    }
  ]
}
```

RAD Agent does not download the locator. At the source-acquisition stage it reads only the
declared local files, verifies workspace confinement and limits, and writes the digest-bound
`.rad-agent-artifacts/sources.json`. Review that artifact and its evidence before later claim
or citation work. PDF, DOCX, remote retrieval, automatic publication, and scientific-quality
judgment are not included in this source-ingestion slice.

## Build a domain-specific executing agent

The RAD Forge Runtime can govern real work after the deployer supplies all of the
following:

- Typed tool descriptors and implementations
- Explicit workspace and network boundaries
- Policy rules for allowed, denied, and approval-gated effects
- Capability evidence for each operation
- Human approval identities and scopes
- Acceptance verifiers that inspect real outputs
- Durable state, recovery bounds, observability, and evidence storage
- A composition root exposing only the intended capabilities

A model proposes plans; it does not grant itself tools, permissions, or a successful
result. Deterministic code and registered verifiers remain authoritative.

## Troubleshooting

### Startup says the model configuration is missing

Set `RAD_AGENT_MODEL_CONFIG` to an existing YAML or JSON profile. The deprecated
`NEXUS_AGENT_MODEL_CONFIG` name remains a compatibility alias.

### The endpoint is rejected

Use an explicit `http://127.0.0.1:PORT/v1`, `http://localhost:PORT/v1`, or IPv6 loopback
address. The bundled local composition intentionally rejects remote hosts, missing ports,
credentials embedded in URLs, query strings, and non-`/v1` paths.

### The model is unavailable

Confirm the model server is running, its port is correct, and the exact model identifier is
loaded. A health check does not replace qualification.

### The model lacks current qualification

Provide a valid, independently attested qualification matching the exact provider, model,
adapter version, permitted uses, and current time. Do not modify the registry or application
to bypass this failure.

### Login fails

Confirm the password file permissions are owner-only, use the original password, and wait
if repeated failures triggered the local rate limit. Tokens do not survive restart.

### The candidate is rejected

The model output must match the strict candidate schema and must not contain tool calls,
unknown fields, non-finite numbers, secret material, or contradictory readiness claims.
Choose a qualified model that reliably produces the required structured output.

### Approval does not execute work

That is expected in the bundled local planning/review application. Execution requires a
separate explicit composition with qualified tools, policy, capabilities, approvals, and
acceptance verifiers.

## Security boundary

- Keep the browser application and model server on loopback.
- Do not expose port 8765 directly to a public network.
- Never commit password files, state directories, API keys, private attestations, or private inputs.
- Treat all model output as untrusted data.
- Require human approval for consequential actions.
- Verify success from recorded outputs and acceptance evidence, not from a model's claim.

See [SECURITY.md](../SECURITY.md) and the [engineering status](runbooks/STATUS.md) before
using RAD Agent for sensitive or production work.
