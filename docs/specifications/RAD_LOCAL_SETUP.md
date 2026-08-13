# RAD Agent Local Setup and Diagnostics Specification

Status: frozen for Phase 1

## Purpose

Provide one supported `rad` command that configures, diagnoses, and starts the local
RAD Agent planning/review application without requiring a new user to hand-write YAML.
Existing `nexus`, `nexus-agent-serve`, and `nexus-model-eval` entry points remain
available as compatibility aliases.

## Commands

- `rad setup` discovers loopback OpenAI-compatible endpoints, requires an explicit model
  selection when discovery is ambiguous, creates private configuration and password files,
  and records either `development` or `qualified` mode.
- `rad doctor` validates settings, file permissions, model configuration, loopback model
  availability, model selection, and qualification requirements without invoking inference.
- `rad serve` loads the generated settings, exports the supported application environment,
  and delegates to the existing loopback server.
- `rad --help` exits successfully and never requires a configured control client.

## Operating modes

### Development

Development mode is an explicit, visibly warned, local-only planning/review mode. It may
authorize only candidate-specification and repair-proposal model uses. It exposes no runtime
tools, does not register or fabricate qualification evidence, and reports no active model
qualification. It must never be described as qualified or production-ready.

### Qualified

Qualified mode preserves the existing fail-closed requirement for a current independently
attested model qualification matching provider, model, adapter version, and requested use.

## Security and compatibility

- Generated directories and password files are owner-only.
- Literal model credentials are never accepted or written; configuration may contain only
  opaque secret references.
- Detection probes only fixed or explicitly supplied loopback `/v1` endpoints.
- Setup never downloads a model, contacts a cloud provider, modifies a model server, or
  creates qualification evidence.
- `RAD_AGENT_MODEL_CONFIG`, `RAD_AGENT_MODEL_ATTESTATION`, and `RAD_AGENT_MODE` are the
  preferred variables. Existing `NEXUS_AGENT_*` variables remain supported with lower
  precedence during migration.
- Existing package imports remain unchanged in Phase 1.

## Acceptance gates

1. `rad --help`, `rad setup --help`, `rad doctor --help`, and `rad serve --help`
   succeed without a control client.
2. Setup produces private, schema-valid configuration from one detected or explicitly
   selected loopback model.
3. Ambiguous, unavailable, remote, malformed, or secret-bearing configuration fails safely.
4. Doctor distinguishes healthy development mode, missing qualification, unavailable model,
   and unsafe password permissions.
5. Development mode cannot authorize execution, tools, sensitive actions, or claim active
   qualification.
6. Qualified mode retains existing exact attestation behavior.
7. Focused unit/integration/security tests, full Python tests, Ruff, strict mypy, contract
   validation, build, and installed entry-point smoke checks pass.
