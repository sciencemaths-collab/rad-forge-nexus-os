# Release Packaging

Status: implemented for RAD Agent Alpha 3.

## Contract

A release tag must exactly equal `v` plus the Python package version. The release workflow
runs the complete qualification bundle before producing or publishing any release. It builds
the wheel and source archive with `SOURCE_DATE_EPOCH`, emits sorted SHA-256 checksums, archives
the evidence deterministically, and creates GitHub build-provenance attestations.

The OCI image uses a digest-pinned official Python base, installs only the prebuilt wheel, runs
as numeric non-root user `10001`, and defaults to `rad --help`. The release workflow builds
`linux/amd64` and `linux/arm64`, generates an SBOM and maximal provenance, pushes the immutable
tag to GHCR, and creates a signed GitHub attestation for the image digest.

No release proceeds after a failed audit, test, package, browser, checksum, image, or
attestation step. Publishing is tag-triggered and uses GitHub's short-lived token; no long-lived
registry or signing key is stored in the repository.
