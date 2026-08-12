# Contributing to RAD Forge / NEXUS OS

Contributions should preserve the runtime's provider-neutral, evidence-driven trust
model. Specifications and machine-readable contracts are authoritative; provider output
and prompts are not.

## Development process

1. Read [`AGENTS.md`](AGENTS.md) and the relevant files in `docs/specifications/`.
2. Open an issue or focused pull request describing the boundary being changed.
3. Add or update contract tests before changing behavior.
4. Implement the smallest change that satisfies the accepted contract.
5. Add unit, integration, security, and failure coverage appropriate to the effect.
6. Update component documentation, evidence, and `docs/runbooks/STATUS.md`.
7. Run the complete verification suite before requesting review.

```bash
uv sync --all-groups --locked
npm ci --prefix sdk/typescript --ignore-scripts
uv run python scripts/validate_contracts.py
uv run ruff format --check .
uv run ruff check .
uv run mypy src scripts
uv run pytest -q
npm test --prefix sdk/typescript
uv build
```

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
