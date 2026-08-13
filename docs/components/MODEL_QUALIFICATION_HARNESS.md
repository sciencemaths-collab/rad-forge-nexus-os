# Component AJ: Reasoning Model Qualification Harness

Status: SPECIFIED | Live status: UNVERIFIED | Boundary contract: 1.0

The harness is a deterministic promotion boundary for reasoning models. It accepts
validated evaluation outcomes with evidence UUIDs, requires exactly one result for
all seven contract categories, and derives Agent proposal uses from the normative
promotion matrix. Missing, duplicated, malformed, limited, and failed results fail
closed for every use that depends on them.

Input ordering cannot change the canonical SHA-256 evidence digest. Expiry is checked
at use time and disables every permission at the exact boundary. A maximum 90-day
validity prevents indefinite trust from stale evaluations.

The harness cannot generate or attest its own evidence and cannot grant tool or
runtime authority. Tests exercise synthetic observations only; no provider endpoint,
model weights, secrets, network client, or live inference is used.
