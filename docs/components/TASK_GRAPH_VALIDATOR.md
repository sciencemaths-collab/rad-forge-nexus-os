# Component E: Task Graph Validator

Status: TESTED | Semantic contract version: 1.0

The validator accepts an immutable compiled graph, rejects every unknown dependency,
detects cycles iteratively, and returns deterministic topological order plus parallel
readiness levels. Alphabetical task-ID ordering removes input-order ambiguity.

The component performs no execution, state transition, persistence, retry, policy,
or provider behavior. Those remain later gated components.
