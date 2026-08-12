# Component L: Workspace Sandbox Authorization

Status: TESTED | Boundary contract: 1.0

`WorkspaceSandbox` is a deny-by-default authorization layer. It fixes one existing,
non-symlink canonical workspace root; rejects absolute, empty, non-normalized,
traversal, NUL, backslash, and symlink-escaping paths; and allows writes only below
explicit relative prefixes. Subprocess environments are rebuilt from a non-secret
key allowlist. Network authorization requires an exact normalized hostname and
valid port, with no hosts allowed by default.

This component does not open files, launch subprocesses, change operating-system
permissions, create containers, or make network requests. Callers must minimize the
time between authorization and use. Race-resistant descriptor-relative opening,
process/resource containment, and deployment-specific network enforcement remain
integration and hardening gates.
