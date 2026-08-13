# Component AK: Controlled Model Evaluation Runner

Status: SPECIFIED | Live status: UNVERIFIED | Boundary contract: 1.0

The runner executes a complete fixed structured-output corpus through any conforming
provider adapter. Suite and report digests bind the exact cases and observations.
Deterministic exact-object rubrics prevent model-authored scores or evidence IDs from
being accepted as evaluator decisions.

Sequential execution, per-case timeouts, strict JSON parsing, duplicate-key rejection,
bounded output, safe failure codes, and raw-output exclusion limit the attack surface.
Category results may be converted to qualification inputs only after independent
evidence UUIDs are supplied for all seven categories.

Automated tests use a queued fake local transport. They open no socket and neither
install nor qualify a live model.
