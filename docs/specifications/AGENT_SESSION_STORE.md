# Durable RAD Agent Session Store

Status: Accepted Phase AQ boundary | Normative

## Purpose

Phase AQ turns the Phase AH Agent schemas into atomic, resumable application state.
Sessions, candidate revisions, lifecycle events, clarification boundaries, review, and
digest-bound approval are persisted without granting a reasoning model execution power.

## Candidate rules

Candidate input is untrusted. It must contain exactly the public schema fields, recompute
to its declared canonical SHA-256 digest, bind the target session, use a monotonically
increasing revision and stable candidate identifier, contain unique acceptance IDs, and
contain no literal secret-like material. A review-ready candidate has no unresolved
questions. Every revision is immutable and retained.

## Lifecycle and concurrency

Every operation supplies the expected final event sequence. A transaction locks the
session, verifies the expected sequence/current state, appends exactly the allowed event,
and updates the session atomically. Events are contiguous, append-only, chronologically
ordered, and immutable. Terminal sessions cannot change.

A non-ready candidate moves `DRAFTING` to `CLARIFICATION_REQUIRED`; a clarification
receipt returns it to `DRAFTING`. A ready candidate moves to `SPECIFICATION_READY`, then
an explicit presentation step moves it to `USER_REVIEW`. Approval requires an externally
authenticated and authorized human principal and exact current candidate digest, and
moves the session to `APPROVED`. Any revision requires returning to drafting and a new
approval.

## Phase AQ non-goals

Phase AQ does not authenticate identities, call a model, interpret conversation, select
a provider, start a runtime run, expose HTTP/UI, execute tools, or infer authorization
from model text.
