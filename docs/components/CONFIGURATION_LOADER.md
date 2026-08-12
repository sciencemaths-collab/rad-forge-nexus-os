# Component A: Configuration Loader

Status: TESTED | Contract version: project schema 1.0

## Responsibility and boundary

`nexus_os.config` reads one explicitly selected YAML or JSON project file, applies
explicit caller-supplied `NEXUS__...` overlays, materializes schema defaults,
validates the result, and returns a canonical configuration plus SHA-256 digest.
It does not resolve secrets, inspect the process environment implicitly, access a
workspace, invoke a provider, or perform any external side effect.

Environment overlay names are deterministic paths separated by double
underscores, for example `NEXUS__POLICY__MAX_ATTEMPTS=7`. An overlay may replace
only a key already present in the input document. Overlay values use YAML scalar
typing and the final document must pass the authoritative JSON Schema.

## Failure and security behavior

- Inputs over 1 MiB, unsupported extensions, malformed encoding/syntax, non-object
  roots, YAML aliases/anchors, unknown keys, invalid formats, and literal secrets
  fail closed as `ConfigError` before a configuration is returned.
- YAML uses a restricted `SafeLoader` subclass. Aliases and anchors are rejected
  to bound expansion and avoid shared-reference ambiguity.
- Secret values remain references only. Redacted manifests remove the reference
  target as well as any resolved value.
- Canonical JSON sorts keys and uses stable separators; its digest is independent
  of supported input serialization.
- Returned data is a defensive copy, so caller mutation cannot alter the canonical
  internal state or digest.

## Qualification limits

This component is TESTED, not production-qualified. The later secrets component
will own reference resolution and non-serializable secret wrappers. The later
sandbox component will own path authorization and race-resistant file opening.
The later evidence ledger will replace the provisional component evidence record
with chained runtime evidence.
