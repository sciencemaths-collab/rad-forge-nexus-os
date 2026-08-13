# NEXUS Agent Product Specification

Status: Accepted Phase AH boundary | Normative

## Purpose

NEXUS Agent is the user-facing product that turns natural-language objectives and
declared inputs into reviewable candidate specifications. NEXUS OS remains the
governing runtime. A reasoning provider supplies untrusted interpretation and
planning proposals but receives no direct execution authority.

## Required boundaries

- Conversation, candidate specification, approved specification, runtime run, and
  evidence records are distinct versioned objects.
- Model output is schema-validated before it can become a candidate specification.
- Only an authenticated authorized actor may approve a candidate specification.
- Approval binds the canonical candidate digest. Any material change requires a new
  digest and a new approval.
- No agent or provider may invoke a tool except through NEXUS OS policy, approval,
  sandbox, and typed-tool boundaries.
- No completion, verification, qualification, or production claim may be inferred
  from model text.
- Local endpoints, organization endpoints, and hosted providers use the same adapter
  and conformance boundary. Credential references remain opaque.

## Session lifecycle

The allowed lifecycle is:

`DRAFTING -> CLARIFICATION_REQUIRED -> DRAFTING`,
`DRAFTING -> SPECIFICATION_READY -> USER_REVIEW`,
`USER_REVIEW -> DRAFTING | APPROVED | CANCELLED`,
`APPROVED -> RUNNING`,
`RUNNING -> APPROVAL_REQUIRED | VERIFYING | FAILED | CANCELLED`,
`APPROVAL_REQUIRED -> RUNNING | FAILED | CANCELLED`,
`VERIFYING -> COMPLETED | FAILED`, and terminal states do not transition.

Session events are append-only, monotonically sequenced, bounded, and free of
resolved secrets. The current state must equal the final event state.

## Candidate specification

A candidate declares an objective, one workflow mode, inputs by opaque artifact
reference, constraints, acceptance criteria, required capabilities, risk summary,
unresolved questions, and whether it is ready for review. Acceptance criteria use
stable identifiers and observable verification methods. Literal credentials and
embedded file contents are prohibited.

## Model qualification

Connecting a model does not qualify it. Qualification records evaluate at least
schema conformance, planning, tool selection, approval-boundary recognition,
evidence grounding, adversarial-input handling, and bounded repair. Each evaluation
records evidence identifiers and a pass, fail, or limited result. Allowed uses are
derived from those results and expire according to policy.

## Phase AH non-goals

Phase AH does not implement conversational inference, local model discovery,
hardware assessment, tool execution, HTTP serving, authentication, persistence,
streaming, desktop/web UI, or live-provider qualification.

## Security requirements

- Reject unknown fields, oversized text, invalid identifiers, noncanonical digests,
  duplicate acceptance identifiers, duplicate event sequence numbers, illegal state
  transitions, and current-state/history mismatch.
- Treat objectives, attachments, retrieved content, and model responses as untrusted.
- Never place secrets, tokens, authorization headers, or resolved credentials in
  session events, candidate specifications, logs, or qualification evidence.
- A clarification response cannot itself authorize execution.
