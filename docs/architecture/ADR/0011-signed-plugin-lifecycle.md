# ADR 0011: Signed, inert-by-default plugin lifecycle

Status: accepted

## Decision

RAD plugin packages are bounded ZIP archives containing exactly `manifest.json`, one payload,
and `signature.ed25519`. A locally configured trust store maps publisher identities to Ed25519
public keys. Installation verifies the canonical manifest signature, payload name, size, digest,
RAD compatibility range, explicit operator-approved permissions, and qualification-attestation
digest before an atomic durable registration.

Installation never imports, installs, or executes the payload. Installed plugins begin disabled.
Enablement is a separate lifecycle operation and still does not register capabilities with RAD
Node. Runtime registration requires the existing policy, approval, and exact capability
qualification gates. Updates are installed side-by-side; one version may be enabled at a time.

## Consequences

A valid signature establishes package integrity and a configured publisher identity; it does not
establish safety, quality, qualification, or execution permission. Trust-store modification is
an operator administration action outside package installation. Registry mutations are atomic
and auditable. Removal deletes only the selected managed package after disabling it; previous
versions remain available for explicit rollback.
