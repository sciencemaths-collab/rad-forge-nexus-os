# Security Policy

## Supported versions

The project has not published a stable production release. Security fixes are applied to
the latest maintained branch and are not backported unless a release notice states otherwise.

## Reporting a vulnerability

Submit a [private security advisory](https://github.com/sciencemaths-collab/rad-forge-nexus-os/security/advisories/new).
Avoid public issues, pull requests, discussions, or logs containing exploit details,
credentials, personal data, or unresolved secret material.

Include the affected component and version, required preconditions, reproducible steps,
observed impact, and a minimal proof of concept. Remove live credentials and production data
before submitting any evidence.

## Response expectations

Maintainers will acknowledge a valid report, assess severity and affected boundaries, define
a remediation plan, and coordinate disclosure after a verified fix. Response timing depends
on impact and maintainer availability; no service-level agreement is currently offered.

## Scope

Relevant reports include authentication or authorization bypasses, sandbox escapes, secret
exposure, policy or approval bypasses, evidence-integrity failures, unsafe deserialization,
injection, dependency compromise, and denial-of-service paths that violate documented bounds.

Provider outages, unsupported provider behavior, social engineering, and findings that require
already-compromised administrator access are generally outside scope unless they expose a separate
vulnerability in RAD Agent or the RAD Forge Runtime.
