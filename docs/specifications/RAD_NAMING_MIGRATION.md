# RAD Agent Naming Migration

Status: Phase 6 in progress.

## Canonical public names

- Product: **RAD Agent**
- Primary command: `rad`
- Model evaluation command: `rad-model-eval`
- Server command: `rad-agent-serve`
- Environment variables: `RAD_AGENT_*`
- Nested project-configuration overlays: `RAD_AGENT__*`

## Compatibility boundary

Existing `nexus-*`, `NEXUS_AGENT_*`, and `NEXUS__*` names remain deprecated aliases during
the compatibility window. If both nested overlay forms target the same setting, the RAD Agent
name takes precedence. The `nexus_os` Python import path, `nexus-os` distribution name,
TypeScript package identifier, deterministic UUID namespace strings, database formats, and
repository slug remain stable until a separately versioned compatibility release.

Public interfaces and current documentation must say RAD Agent. Historical ADRs and status
evidence may retain the names that were accurate when those records were created.

## Acceptance

1. New setup and help paths use only canonical RAD Agent names.
2. New and legacy environment names load the same validated configuration.
3. Canonical RAD Agent values win deterministic precedence conflicts.
4. Existing commands, imports, stored IDs, and installed configurations continue to work.
5. Lint, type, unit, security, SDK, packaged, and browser gates pass.
