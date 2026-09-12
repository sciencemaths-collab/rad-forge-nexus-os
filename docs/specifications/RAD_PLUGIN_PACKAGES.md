# RAD Plugin Packages 1.0

Status: implemented local installer and lifecycle; no public marketplace catalog.

## Package and trust contract

A `.radplug` is a bounded ZIP containing exactly three regular files:

- `manifest.json`, following `schemas/plugin-manifest.schema.json`;
- one payload whose filename, byte count, and SHA-256 digest match the manifest; and
- `signature.ed25519`, a 64-byte Ed25519 signature over canonical manifest JSON.

The operator supplies a local trust store. RAD resolves `publisher_id` to a raw Ed25519 public
key and rejects unknown publishers, malformed keys, invalid signatures, duplicate JSON keys,
archive traversal, links, duplicate or additional members, oversized content, incompatible RAD
versions, payload mismatches, and inconsistent qualification declarations.

A trust store is explicit local policy, not package content:

```json
{
  "schema_version": "1.0",
  "publishers": {
    "example.publisher": "BASE64_RAW_32_BYTE_ED25519_PUBLIC_KEY"
  }
}
```

## Installation and lifecycle

Installers must repeat every requested permission exactly. No permission is inferred:

```bash
rad plugins install example.radplug \
  --trust-store ~/.config/rad/trusted-publishers.json \
  --qualification ./qualification.json \
  --approve-permission workspace.read

rad plugins list
rad plugins enable example.plugin 1.0.0
rad plugins disable example.plugin 1.0.0
rad plugins uninstall example.plugin 1.0.0
```

Installation verifies and atomically copies the payload into private managed storage. It begins
`DISABLED`. Enable, disable, and uninstall are explicit audited transitions. Enabling one version
disables other versions of the same plugin, providing side-by-side upgrade and explicit rollback.
Uninstall requires a disabled plugin and targets only its managed version.

## Permission and execution boundary

Declared permissions are `workspace.read`, `workspace.write`, `network`, `secrets`, and
`external.action`. Permission review records operator consent to installation; it does not grant
runtime authority. Installation and enablement never import, execute, or `pip install` payloads.
An enabled package reports `execution_authorized: false`.

Executable activation requires a separately implemented adapter loader to revalidate the package,
isolate its process, map declared permissions into policy, register exact capability manifests,
verify qualification attestations semantically, and route through RAD Node. Until that loader is
qualified, plugins are secure distributable artifacts and lifecycle records—not executable code.

There is no public marketplace catalog in this release. Publishers distribute `.radplug` files
and public keys independently; operators control their trust stores. A future catalog must add
signed index metadata, publisher onboarding/revocation, transparency, moderation, and update
channels without weakening this installer contract.
