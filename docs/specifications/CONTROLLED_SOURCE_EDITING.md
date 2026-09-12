# Controlled Source Editing

Status: implemented for RAD Agent Phase 8C.

## Contract

- Only the app-build implementation stage may invoke `workspace.apply_text_changes`.
- The stage is `SENSITIVE`; execution requires a human approval bound to the exact action digest.
- The model proposes at most 32 complete UTF-8 replacements using relative paths, expected prior
  SHA-256 digests, and content. A null prior digest is valid only for a new file.
- Traversal, hidden paths, secret-like names or content, symlinks, binary content, stale digests,
  duplicate paths, and size-budget violations fail before mutation.
- No deletion, shell command, network request, deployment, or publication is supported.
- Applied files are atomic replacements. A private rollback record preserves original content and
  an independently downloadable implementation summary records final digests.
- Replaying the same approved action is accepted only when every final digest still matches.

## Acceptance gates

1. Exact updates and new files succeed only after the approved structured proposal.
2. Stale, unsafe, secret-bearing, symlinked, or conflicting changes leave source unchanged.
3. Rollback evidence binds original content, prior digest, final digest, and proposal digest.
4. The implementation stage is approval-gated and later test stages remain blocked until it
   succeeds.
