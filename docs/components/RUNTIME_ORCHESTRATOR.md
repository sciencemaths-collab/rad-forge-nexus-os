# Component G: Runtime Orchestrator

Status: TESTED | Runtime snapshot contract: 1.0

The provider-neutral orchestrator advances validated task graphs through legal run
and task states. Each accepted mutation writes a complete immutable snapshot using
the checkpoint store's optimistic revision guard. Dependency readiness is derived
deterministically; duplicate or out-of-order dispatch and stale writers fail before
overwriting durable state.

Cancellation records the required `CANCELLING` stage before terminal cancellation.
Resume requires the same graph digest and schema version and validates the complete
task set. Provider dispatch, retry/repair, policy, approval, and evidence chaining
remain outside this component.
