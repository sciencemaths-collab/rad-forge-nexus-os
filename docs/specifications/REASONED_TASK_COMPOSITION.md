# Reasoned Task Composition

Phase 4B joins qualified, proposal-only task reasoning to governed typed-tool execution without giving the model control of dispatch.

For each exact `(run_id, task_id, approved task digest)`, RAD Agent stores one immutable canonical reasoning artifact and its digest. Preparation fails closed when questions remain unresolved or the approved input collides with reserved composition fields. Resolution revalidates the complete binding and enriches the original input with only `reasoned_artifact` and `reasoned_artifact_digest`.

The scheduler uses the same resolved payload for preview and execution. Deterministic code still selects the tool, validates its schema and effect, evaluates policy, requests any required approval, executes through the typed-tool boundary, and records evidence. Model output cannot select a tool, bypass policy, approve an action, execute a command, or claim verification.

This slice does not expose preparation through HTTP or the browser and does not qualify a live provider. Those remain later integration and qualification work.
