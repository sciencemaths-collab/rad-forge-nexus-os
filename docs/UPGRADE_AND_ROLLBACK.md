# Upgrade and Rollback

## Before upgrading

1. Stop RAD Agent.
2. Copy `.rad-agent/` and the selected workspace's `.rad-agent-artifacts/` to protected backup
   storage.
3. Download the target release, `SHA256SUMS`, and GitHub provenance attestation.
4. Verify the checksum and attestation before installation.

## Upgrade to Alpha 3

```bash
pipx upgrade nexus-os
rad doctor
```

The Alpha 3 project configuration schema remains `1.0`. To validate and materialize a private,
canonical copy without overwriting the source:

```bash
rad-config-migrate project.yaml project.v1.json --from-version 1.0 --to-version 1.0
```

Unsupported version paths fail closed. Never edit the schema version to bypass validation.

## Roll back

Stop the application, reinstall the exact previous attested wheel, and restore the matching
`.rad-agent/` backup:

```bash
pipx install --force ./nexus_os-PREVIOUS_VERSION-py3-none-any.whl
rad doctor
```

Do not open newer state databases with an older release unless that release explicitly lists
the database version as compatible. Preserve newer state and evidence rather than deleting or
rewriting it. A failed `rad doctor` is a stop condition, not permission to weaken validation.

## Container rollback

Deploy images by immutable digest, not a moving tag. Record the prior digest before upgrade;
rollback means redeploying that exact digest and its matching configuration backup.
