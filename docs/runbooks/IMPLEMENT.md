# Implementation Runbook

## Setup and baseline

```bash
uv sync --all-groups
uv run python scripts/validate_contracts.py
uv run ruff check .
uv run mypy src
uv run pytest
```

Before work, inspect status and overlapping user changes. Select the next pending
component in `STATUS.md`, restate its contract and threats, and add failing contract
tests. Implement the smallest compliant boundary. Run focused unit tests, then
affected contract, integration, security, and resilience tests. Never run live
provider tests without explicit opt-in and scoped credentials.

Record commands, environment, test IDs, input/output digests, trace ID, and outcome
in evidence. Update status with actual qualification and limitations. Review the
diff for secrets, generated noise, TODO/fake behavior, and contract drift. Commit a
focused change. If Git is unavailable, mark the gate blocked and do not claim it.

On failure, classify it. Repair only within configured attempt/time/budget bounds.
Do not retry policy denial, invalid approval, or repeat deterministic failures
without a changed input/implementation. Stop on destructive, costly, production,
external-user, permission-escalation, or scope-changing actions.

