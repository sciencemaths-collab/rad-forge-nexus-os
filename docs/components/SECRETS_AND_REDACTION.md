# Component K: Secrets and Redaction

Status: TESTED | Boundary contract: 1.0

Secret configuration remains reference-only. `SecretReference` accepts bounded
`env:`, `vault:`, and `secret:` locators; `SecretResolver` resolves only through
explicitly supplied environment data or backend functions. Resolved values use a
non-serializable, redacted wrapper with scoped close and best-effort buffer clearing.

The recursive redactor produces a separate safe value, detects exact canaries,
sensitive key names, opaque references, common credential formats, cycles, and
excessive nesting. It is the required boundary before logs, evidence, errors, or
other serializable diagnostic outputs.

Python cannot guarantee removal of every immutable string copy from process memory.
Host isolation, backend authentication, adapter-specific credential scoping, and
subprocess environment filtering remain later integration and sandbox gates.
