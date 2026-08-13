# RAD Agent Phase 2: Model connections

Status: implemented local-provider slice

## Purpose

Phase 2 turns the Phase 1 model endpoint into an explicit, inspectable connection.
It supports Ollama, LM Studio, and other loopback OpenAI-compatible servers without
binding the governed runtime to a vendor SDK.

## User contract

- `rad setup` accepts `--provider auto|ollama|lm_studio|local_openai`.
- Auto-detection identifies Ollama on port 11434, LM Studio on port 1234, and
  other explicit loopback `/v1` endpoints as generic OpenAI-compatible servers.
- `rad models list` displays configured profiles with credential references redacted.
- `rad models test` checks model discovery and fails closed if the selected model
  is not reported.
- `rad doctor` continues to check the same connection as part of whole-application
  readiness.
- Model use remains either visibly unqualified development mode or exact-attestation
  qualified mode. Connecting a model never qualifies it.
- Credentials remain opaque `env:`, `file:`, or `keyring:` references. Literal
  secrets are rejected.

## Safety and trust boundaries

Only explicit loopback URLs ending in `/v1` are accepted in this slice. Redirects,
remote hosts, embedded credentials, queries, fragments, and ambiguous provider
selection are rejected. Provider responses are size-bounded and schema-validated.
Connection tests perform discovery only and never invoke inference.

The provider type is part of the qualification identity. An Ollama attestation does
not authorize an LM Studio or generic OpenAI-compatible profile.

## Deferred cloud slice

Direct OpenAI and Anthropic connections require separate outbound-network policy,
provider-specific transport contracts, opt-in live tests, and credential handling.
They are intentionally not presented as available here until those gates exist.
Existing provider adapters remain internal and unverified for live production use.

## Verification

Unit tests cover provider identification, mismatch rejection, credential-reference
redaction, discovery reporting, unavailable-model failure, and unsupported types.
The repository's complete release gates remain authoritative.
