# Agent Model Configuration

Status: frozen for Component AZ

## Purpose

Component AZ lets an operator select the language model used for NEXUS Agent
reasoning without turning provider availability into execution authority. The
initial supported product profile is a credential-optional, OpenAI-compatible
server bound to loopback, including local runtimes such as Ollama, LM Studio, or
another compatible implementation.

## Contract

- Configuration is bounded JSON or YAML with one selected profile, no unknown
  fields, aliases, anchors, embedded credentials, or non-loopback endpoint.
- A profile binds type, explicit `/v1` endpoint, optional model identifier,
  optional opaque credential reference, exact adapter version, and timeout.
- If the model identifier is omitted, `/v1/models` discovery may select it only
  when exactly one bounded, unique model is returned. Multiple or zero models
  require an explicit operator choice.
- Discovery proves availability only. Before use, the exact provider, model, and
  adapter version must have current registry evidence permitting both candidate
  specification and bounded repair.
- Credentials are resolved for the shortest transport scope, never serialized,
  and represented as a redacted reference in public configuration views.
- Provider health must pass after qualification. Failure at configuration,
  discovery, credential, qualification, or health boundaries prevents startup.
- Configuration and discovery never invoke inference, tools, approvals, or work.

## Exclusions

AZ does not install model weights, recommend a model, grant qualification from a
model name, support public endpoints, or assemble the complete runtime. Remote
cloud adapters remain available behind existing provider-neutral ports but are
not exposed through this local-first product profile until their live transport
and qualification path receives its own gate.

## Acceptance gates

1. Explicit and single-discovered qualified models resolve without inference.
2. Unqualified, unavailable, ambiguous, malformed, non-loopback, unknown-field,
   alias-bearing, or literal-secret configurations fail closed.
3. Discovery responses are bounded, sorted, unique, and schema checked.
4. Secrets reach only transport calls and never public manifests.
5. Full release evidence and installed-package imports pass.
