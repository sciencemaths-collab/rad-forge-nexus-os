# ADR 0007: Financial Algorithm as the first RAD decision capability

Status: Accepted

## Decision

RAD integrates Financial Algorithm as a qualified domain pack rather than embedding financial
logic in the kernel. The initial binding is engine 0.2.0, adapter 1.0.0, and capability
`rad.decision.financial`. RAD retains governance, approval metadata, qualification, routing,
lifecycle, and evidence controls; the independent package owns its financial computations.

The capability is deliberately non-transactional. Every response denies execution authority and
the operation allowlist contains no broker or order action. A separate future execution capability
must carry sensitive/destructive effects, broker-specific controls, risk limits, human approval,
paper-trading evidence, and regulatory review.

PathWoven remains independently routable. Cross-engine financial optimization will require a new
strict data objective and its own qualification; arbitrary code injection is not an acceptable
integration mechanism.
