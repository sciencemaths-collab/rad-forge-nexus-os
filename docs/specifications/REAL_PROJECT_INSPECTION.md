# Real Project Inspection

Status: implemented for RAD Agent Phases 8A-8B.

## Purpose

The bundled runtime must inspect an operator-approved software workspace before it proposes
implementation work. Phase 8A adds deterministic, read-only source inspection whose only write
is its governed inventory artifact; it does not
grant shell, network, deployment, or arbitrary file-reading authority.

## Contract

- `workspace.inspect_project` accepts only an existing real workspace directory.
- Traversal, symlinked files/directories, secret-like names, hidden state, VCS metadata,
  dependency trees, binary content, and oversized projects are excluded or rejected.
- Results contain normalized relative paths, byte sizes, SHA-256 digests, and a bounded UTF-8
  preview. They never contain absolute paths.
- The inventory is written atomically as `.rad-agent-artifacts/project-inventory.json` and is independently
  digestible as evidence.
- App-build `specification` is the only stage bound to this tool in Phase 8A.
- No command is executed and no project source file is modified.

## Reasoning context contract

- Later app-build stages receive a deterministic subset of the inventory through an optional
  provider-neutral task-context boundary.
- Before returning context, the provider rechecks the inventory schema and every recorded file's
  real path, size, and SHA-256 digest. Missing, changed, symlinked, or malformed content fails
  closed instead of reaching the model.
- Context is capped at 48 KiB, sorted by relative path, contains no absolute paths, and reports
  whether the inventory was truncated for the prompt.
- The initial specification/inspection task receives no project context because it creates the
  inventory. Non-app modes and non-local composition remain unchanged.

## Acceptance gates

1. A small real project produces a stable, sorted inventory artifact.
2. Symlinks, traversal, binary content, secret-like files, excessive counts, and excessive
   bytes cannot escape the boundary or enter the inventory.
3. The reference app-build runtime binds inspection before later write stages.
4. Existing release, type, lint, security, and browser gates remain green.
5. A changed or symlinked file is rejected before a later model request.
