# Component N: Capability Qualification

Status: TESTED | Boundary contract: 1.0

Qualification is a deterministic function of a versioned rule and an integrity-
verified evidence chain. Rules declare required evidence kinds, minimum passing
records, distinct test identities, target state, and optional validity. Non-passing,
missing, duplicate-test, future-dated, or integrity-invalid evidence cannot promote
a capability. Automatic rules are capped at `QUALIFIED`; production states cannot
be granted by this component.

This component does not approve releases, authenticate reviewers, decide provider
fitness, or persist qualifications. Those require later operating, provider, and
release gates.
