# Contributing to RAD Agent

Thank you for helping improve RAD Agent. Contributions are welcome across the runtime, provider
adapters, domain capabilities, SDKs, documentation, testing, and security.

Contributions should preserve the runtime's provider-neutral, evidence-driven trust
model. Specifications and machine-readable contracts are authoritative; provider output
and prompts are not.

## Development process

1. Read the relevant files in `docs/specifications/`.
2. Open an issue or focused pull request describing the boundary being changed.
3. Add or update contract tests before changing behavior.
4. Implement the smallest change that satisfies the accepted contract.
5. Add unit, integration, security, and failure coverage appropriate to the effect.
6. Update component documentation, evidence, and `docs/runbooks/STATUS.md`.
7. Run the complete verification suite before requesting review.

```bash
uv sync --all-groups --locked
npm ci --prefix sdk/typescript --ignore-scripts
mkdir -p artifacts/contributor-release-evidence
uv run python scripts/release_evidence.py \
  --root . \
  --output artifacts/contributor-release-evidence
```

This fail-fast command runs formatting, linting, strict typing, schema validation, dependency
audits, unit, contract, integration and security tests, deterministic qualification, package and
clean-wheel checks, browser acceptance, SDK tests, and the repository secret scan. Its generated
evidence is local build output and should not be committed.

## Reporting errors

Search the existing GitHub issues before filing a new defect. Use the structured bug-report
form and provide enough information for another contributor to reproduce the failure:

- affected release, package version, or commit SHA
- operating system and architecture
- Python, `uv`, Node.js, and npm versions when relevant
- installation method and configuration mode
- exact command, SDK call, API operation, or workflow stage
- minimal input or configuration with secrets and private data removed
- expected behavior and observed behavior
- complete reproduction steps from a clean state
- relevant logs, stack traces, exit codes, request IDs, trace IDs, and evidence IDs
- whether the failure is consistent or intermittent
- any safe workaround already attempted

Format logs and commands as code blocks. Prefer text over screenshots because text can be
searched and quoted during diagnosis. Reduce large examples to the smallest failing case and
attach only the artifacts necessary to reproduce the problem.

Never place credentials, access tokens, resolved secrets, personal information, proprietary
datasets, or production records in a public issue. Report suspected vulnerabilities through
the private process documented in [`SECURITY.md`](SECURITY.md).

## Engineering requirements

- Keep vendor SDKs outside core packages and behind adapter contracts.
- Treat model and external output as untrusted input.
- Keep deterministic work in deterministic code.
- Store secret references rather than resolved secret values.
- Require policy evaluation and approval for high-impact effects.
- Preserve atomic, observable, and resumable durable transitions.
- Keep repair bounded by attempt, time, repetition, and cost limits.
- Never weaken tests or acceptance criteria to obtain a pass.

## Pull requests

Focused pull requests are easier to verify and review. Include the motivation, affected
contract, security implications, test evidence, behavior limitations, and migration impact.
Generated dependencies, caches, build output, credentials, and unrelated formatting changes
must not be committed.

By contributing, you agree that your contribution is licensed under the MIT License.
