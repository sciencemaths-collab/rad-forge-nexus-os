# Component AF: CI and Release-Evidence Automation

Status: TESTED | Boundary contract: 1.0

The least-privilege GitHub Actions workflow installs locked Python and TypeScript
dependencies, runs the fail-fast release-evidence generator, uploads its bundle, and runs
GitHub Dependency Review at moderate severity on pull requests. No provider credentials,
deployment permissions, package-publishing permissions, or write-scoped token are present.

The generator executes format, lint, typing, schema, unit, contract, integration, security,
provider-conformance, RW-100K, TypeScript, build, and repository secret-scan gates in order.
It stops on the first failure but still writes a blocked report. Successful automation emits
JSON/Markdown evidence, known limitations, a release checklist, build provenance, and a
CycloneDX 1.6 inventory derived from both lockfiles.

Automated success is not release authorization: generated evidence always leaves clean-room
qualification, independent review, owner approval, and `release_candidate` false. Component
AG owns those remaining proof gates. Dependency Review on a private repository requires the
repository/organization’s applicable GitHub Advanced Security entitlement; absence of that
capability is an external blocking gate, not a reason to make vulnerability review advisory.
