# ADR 0006: PathWoven as the first RAD optimization capability

Status: Accepted

## Decision

RAD integrates PathWoven-DCGO as a versioned Capability Protocol engine operation rather than
embedding its algorithm in the RAD kernel. The initial binding is engine 0.2.0, adapter 1.0.0,
and capability `rad.optimization.pathwoven`. The package remains independently buildable and
qualifiable; RAD owns governance, routing, lifecycle, and evidence controls.

The trust boundary is fail closed at two layers. The adapter requires the exact digest-verified
formal engine qualification report and validates every request and response. RAD Node separately
requires an exact capability qualification before routing. Only built-in objective identifiers
cross the boundary; executable functions and source text do not.

This preserves RAD's original app-building and governed-agent functions while allowing it to
orchestrate specialized engines. Later engines must use their own versioned adapters,
qualification artifacts, and capability IDs rather than weakening this contract.
