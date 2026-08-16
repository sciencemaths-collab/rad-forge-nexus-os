# Durable Model Qualification Registry

Status: Accepted Phase AP boundary | Normative

## Purpose

Phase AP persists a Phase AO attested model qualification and provides an exact,
fail-closed lookup for proposal use. Registration re-verifies every canonical digest;
the database is not a trust boundary and stored documents are checked again when read.

## Registration and replacement

A registry entry is bound to the exact provider, model, and adapter-version tuple. The
attestation must be current at registration time and its qualification must not predate
the attestation. Registration is atomic. A newly registered qualification supersedes
the currently active entry for the same tuple; it never changes or deletes the prior
record. Qualification and attestation identifiers are globally unique.

## Lookup and revocation

Lookup requires an exact tuple and a Phase AJ model use. It succeeds only for one
active, unexpired qualification whose derived allowed uses contain that use. Expired,
revoked, superseded, missing, ambiguous, malformed, or digest-invalid records deny use.
Revocation is an atomic one-way transition of an active record and records bounded,
non-secret actor, time, and reason fields.

## Authority boundary

Successful lookup permits only the named reasoning-model proposal use. It does not
authorize a tool, bypass policy or approval, execute a task, select a trusted attestor,
or promote any capability to production.

## Phase AP non-goals

Phase AP does not authenticate registry operators, create or sign attestations, run a
model, schedule re-evaluation, distribute revocations, expose HTTP/UI endpoints, or
implement the RAD Agent controller.
