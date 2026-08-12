# Trust Model

NEXUS trusts verifiable processes, not provider assertions. Evidence is typed,
content-addressed, linked to a run/task/trace, and verified before qualification.

Capability states are `UNKNOWN`, `IMPLEMENTED`, `TESTED`, `VERIFIED`, `QUALIFIED`,
`PRODUCTION_CANDIDATE`, `PRODUCTION`, and `DEGRADED`. `IMPLEMENTED` requires a
traceable implementation artifact. `TESTED` requires passing required tests.
`VERIFIED` requires independently verifiable evidence with intact provenance.
`QUALIFIED` requires the capability-specific matrix across correctness, security,
resilience, and documentation. `PRODUCTION_CANDIDATE` adds clean-room and release
evidence. `PRODUCTION` requires authorized release approval and operational
readiness. Any invalidated prerequisite or material regression yields `DEGRADED`.

Promotions are monotonic only while prerequisites remain valid and are computed by
versioned deterministic rules. No LLM, provider adapter, or ordinary API caller can
set a state directly. Requalification records a new decision; it never edits prior
evidence. Trust reports name the scope, environment, provider/version, rule version,
evidence IDs, expiry, limitations, and degradation triggers.

