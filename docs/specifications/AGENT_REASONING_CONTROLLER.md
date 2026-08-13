# NEXUS Agent Conversational Reasoning Controller

Status: Accepted Phase AR boundary | Normative

## Purpose

Phase AR converts a durable session objective into an untrusted candidate proposal by
composing an exact qualified model, a provider adapter, and the Phase AQ store. The
controller has no tool, approval, runtime-start, or production authority.

## Controlled inference

Before every provider call, the controller requires the Phase AP registry to authorize
the exact provider/model/adapter tuple for `candidate_specification`. Requests contain a
fixed system contract and the bounded objective only. Provider output must be one strict
JSON object with exactly the candidate proposal fields; unknown fields, duplicate keys,
non-finite values, secret-like content, oversized output, and direct execution/tool
instructions are rejected.

The controller supplies session identity, candidate identity, revision, schema version,
and canonical digest. It never trusts the model to set those fields. A valid proposal is
parsed through Phase AQ and atomically persisted. Missing information produces a
clarification-required candidate; a review-ready proposal produces specification-ready.

## Bounded repair

At most one repair call is allowed, and only when the same exact qualification also
permits `repair_proposal`. The repair prompt contains a fixed safe error code, never raw
exception text or the invalid model output. Provider failures leave the durable session
unchanged.

## Phase AR non-goals

Phase AR does not preserve free-form chat transcripts, authenticate users, approve a
candidate, execute tools, start a run, choose among models, discover/download a model,
stream output, expose HTTP/UI, or claim live-model quality.
