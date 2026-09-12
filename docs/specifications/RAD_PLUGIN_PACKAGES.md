# RAD Plugin Packages 1.0

Status: implemented local installer and lifecycle; no public marketplace catalog.

## Package and trust contract

A `.radplug` is a bounded ZIP containing exactly three regular files:

- `manifest.json`, following `schemas/plugin-manifest.schema.json`;
- one WebAssembly payload whose filename, byte count, and SHA-256 digest match the manifest; and
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
runtime authority. Installation and enablement never import or `pip install` payloads. An enabled
package still reports `execution_authorized: false`; a qualified runtime route is also required.

Executable activation is available for `wasm-v1` packages with zero host permissions. The loader
revalidates managed payload integrity and a canonical, unexpired qualification attestation; denies
all WebAssembly imports and WASI; applies fuel, linear-memory, and JSON I/O bounds; and exposes an
approval-required, qualification-required, read-only capability for RAD Node routing. It cannot
access the filesystem, network, environment, secrets, subprocesses, or external systems.

There is no public marketplace catalog in this release. Publishers distribute `.radplug` files
and public keys independently; operators control their trust stores. A future catalog must add
signed index metadata, publisher onboarding/revocation, transparency, moderation, and update
channels without weakening this installer contract.

### `wasm-v1` ABI

The module exports `memory`, `alloc(i32) -> i32`, and `handle(i32, i32) -> i64`. RAD writes a
canonical `{"operation": ..., "payload": ...}` document at the address returned by `alloc`.
`handle` returns `(output_pointer << 32) | output_length`; the referenced bytes must be a bounded
UTF-8 JSON object. Missing exports, traps, fuel exhaustion, invalid pointers, excess memory,
malformed JSON, duplicate keys, or host imports fail closed.
