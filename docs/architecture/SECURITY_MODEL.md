# Security Model

Security is deny-by-default, least-privilege, and effect-aware. Inputs from users,
repositories, providers, MCP servers, model output, files, and networks are
untrusted until validated. Authentication proves identity; authorization evaluates
actor, project, action digest, resource, data class, environment, and policy.

Actions are classified `READ_ONLY`, `WORKSPACE_WRITE`, `SENSITIVE`, or
`DESTRUCTIVE`. Production deployment, external communication, spending, package
publication, production database mutation, data deletion, and security weakening
always require explicit approval. Approval is scoped to an immutable action digest,
actor, project, expiry, and optional one-use nonce.

Secret config accepts only references (`env:`, `vault:`, `secret:`). Resolved
values are held for the shortest possible lifetime in non-serializable wrappers,
never logged/evidenced/checkpointed, and redacted using exact canaries plus key-name
and format detection. Provider credentials are scoped per adapter and never passed
to repository-controlled subprocesses by default.

The sandbox canonicalizes paths, rejects traversal and symlink escape, scopes file
access to declared roots, restricts subprocess environment, and denies network
unless host/operation policy permits it. Resource limits cover time, memory,
processes, output, requests, tokens, and cost. Audit/evidence records contain safe
metadata and digests, not sensitive payloads.

Security tests are release-blocking. Vulnerability handling, key rotation, incident
response, and disclosure procedures must be completed before production status.

