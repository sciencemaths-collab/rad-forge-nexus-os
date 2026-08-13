# RAD Agent Phase 2B: Official cloud model connections

Status: implemented; live use remains exact-model qualification gated

## Supported providers

RAD Agent can connect directly to the official OpenAI and Anthropic APIs. Cloud profiles use
fixed HTTPS origins; arbitrary remote hosts and endpoint overrides are rejected.

```yaml
schema_version: "1.0"
selected: cloud
profiles:
  cloud:
    type: openai
    base_url: https://api.openai.com/v1
    model: gpt-5
    credential: env:OPENAI_API_KEY
    adapter_version: "1.0"
    timeout_seconds: 30
```

For Anthropic, use `type: anthropic`,
`base_url: https://api.anthropic.com/v1`, and an opaque credential such as
`env:ANTHROPIC_API_KEY`. Anthropic profiles may set `max_tokens`.

## Commands

```bash
uv run rad setup --provider openai --model MODEL \
  --credential-ref env:OPENAI_API_KEY
uv run rad models test
uv run rad doctor
uv run rad serve
```

Replace `openai` and the credential name for Anthropic. Setup writes only the reference,
not the secret. `rad models test` performs authenticated model discovery without inference.

## Runtime contract

- OpenAI uses the Responses API with `store: false` and synchronous proposal generation.
- Anthropic uses the Messages API with the required API-version header.
- Both adapters normalize bounded output text and token usage into the provider-neutral
  result contract.
- HTTP requests are size-bounded, timeout-bounded, non-redirecting, JSON-only, and pinned to
  the provider's official hostname.
- Raw provider errors and credentials do not cross the transport boundary.
- Reachability is not qualification. Qualified mode requires an exact provider, model,
  adapter-version, and use attestation.
- Development mode remains visibly unqualified and proposal-only.

## Verification levels

Default CI uses fake transports for deterministic unit, security, controller, and
conformance tests. It never requires or prints cloud credentials. Optional live discovery
tests require both an explicit opt-in flag and a runtime secret:

```bash
RAD_LIVE_OPENAI=1 OPENAI_API_KEY=... uv run pytest \
  tests/live/test_cloud_model_discovery.py -k openai
RAD_LIVE_ANTHROPIC=1 ANTHROPIC_API_KEY=... uv run pytest \
  tests/live/test_cloud_model_discovery.py -k anthropic
```

Passing repository CI establishes implementation conformance, not independent live-model
quality qualification or production authorization.
