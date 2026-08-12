# Component AF: CI and Release-Evidence Automation

Status: TESTED | Boundary contract: 1.0

The least-privilege GitHub Actions workflow installs locked Python and TypeScript
dependencies, runs the fail-fast release-evidence generator, and uploads its bundle. The
generator runs blocking Python and npm advisory audits. No provider credentials,
deployment permissions, package-publishing permissions, or write-scoped token are present.

The generator executes format, lint, typing, schema, Python dependency audit, npm dependency
audit, unit, contract, integration, security, provider-conformance, RW-100K, TypeScript, build,
and repository secret-scan gates in order.
It stops on the first failure but still writes a blocked report. Successful automation emits
JSON/Markdown evidence, known limitations, a release checklist, build provenance, and a
CycloneDX 1.6 inventory derived from both lockfiles.

Automated success is not release authorization: generated evidence always leaves clean-room
qualification, independent review, owner approval, and `release_candidate` false. Component
AG owns those remaining proof gates. The portable audits replace GitHub Dependency Review,
which the hosted AF run proved unavailable without a private-repository Advanced Security
entitlement; vulnerability review remains blocking rather than becoming advisory.
