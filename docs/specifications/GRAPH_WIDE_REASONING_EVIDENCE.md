# Graph-Wide Reasoning Evidence

Phase 4D binds multi-task recovery and completion verification to the exact reasoning payload executed for every task.

The authenticated preparation manifest lists every task in deterministic topological order with its runtime state, preparation state, and validated artifact digest. This permits restart-safe recovery without invoking the model again for already prepared work.

The scheduler records success evidence from the same resolved payload used by preview and typed-tool execution. When qualified composition is active, final completion recomputes each expected prepared payload digest and requires an exact match with that task's append-only success evidence before any acceptance criterion can pass.

Missing preparation records, task drift, stored-artifact corruption, base-input-only evidence, or a digest mismatch fail closed. The model still cannot select a tool, approve an effect, write evidence, or declare verification.
