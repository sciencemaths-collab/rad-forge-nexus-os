# RAD Forge / NEXUS OS

RAD Forge / NEXUS OS is a specification-first, provider-neutral autonomous work
runtime originated by Bernard Kwadwo Essuman. A user supplies a goal, project
configuration, workspace, provider credentials by reference, policies, and
acceptance criteria. NEXUS compiles bounded work, executes it through replaceable
providers and deterministic tools, checkpoints progress, requests approvals for
sensitive effects, and qualifies results from tamper-evident evidence.

This repository is in **foundation status**. File presence is not proof of a
working or trusted capability. Current qualification is tracked in
[`docs/runbooks/STATUS.md`](docs/runbooks/STATUS.md).

## Modes

- `app_build`: builds and verifies software artifacts.
- `research`: produces traceable research artifacts with source and claim lineage.
- `data_analysis`: computes deterministic analytical artifacts, then permits
  grounded model explanation of those artifacts.

All modes share one kernel: configuration, task graphs, durable execution,
policies, approvals, adapters, tools, evidence, and qualification.

## Foundation layout

- `docs/specifications/`: normative product, implementation, protocol, acceptance,
  and mode requirements.
- `docs/architecture/`: architecture, trust, security, threat, provider, and
  observability designs plus ADRs.
- `schemas/`: JSON Schema contracts.
- `contracts/`: OpenAPI and MCP contracts.
- `tests/`: test suites separated by verification purpose.
- `src/nexus_os/`: runtime implementation (added only after contract gates pass).

## Development

Prerequisites: Python 3.12+ and `uv`.

```bash
uv sync --all-groups
uv run pytest
```

No live provider test runs by default. Live tests require explicit opt-in,
configured secret references, and a trusted CI environment.

## Trust statement

An LLM may propose a plan or completion result, but it cannot promote a
capability. Only deterministic qualification rules over verified evidence can do
so. The meanings of `IMPLEMENTED`, `TESTED`, `VERIFIED`, `QUALIFIED`, and
production states are specified in the trust model.

## License

No license has yet been selected. Until the owner chooses one, all rights are
reserved; this repository must not be presented as open source.

