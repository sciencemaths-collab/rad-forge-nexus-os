# Release Runbook

Releases are authorized evidence bundles, not tags alone. Freeze contracts, create
a clean checkout, install only from documented instructions, and run format, lint,
typecheck, schema, unit, contract, integration, security, resilience, e2e,
benchmark, RW-100K, CLI/SDK, package, and documentation-behavior tests.

Verify the evidence chain; scan source, logs, artifacts, and build output for secret
canaries; generate SBOM/provenance where supported; review dependency and license
findings; and produce `final-evidence-report.json`, its Markdown rendering,
`KNOWN_LIMITATIONS.md`, and `RELEASE_CANDIDATE_CHECKLIST.md`.

Live provider tests are isolated, opt-in jobs using least-privilege environments.
They may qualify a specific adapter/provider/version but are not required for mock
kernel qualification. Repository pull-request code must not receive broad provider
credentials.

Production deployment, package publication, external announcements, and promotion
to `PRODUCTION` require explicit owner/release approval bound to the artifact and
evidence digests. A failed or incomplete gate stops release; it is not waived by
renaming the release or marking the test optional.

