# Qualified task reasoning boundary

Status: Accepted Phase 4A boundary | Normative

## Purpose

Phase 4A lets an exactly qualified reasoning model propose structured content for one
already-approved runtime task. It is a proposal boundary only: it does not register or invoke
a tool, write a file, alter a task graph, update capability state, or claim task completion.

## Authorization and input

- Read-only and workspace-write tasks require exact `task_planning` model authorization.
- Sensitive or destructive tasks require exact `sensitive_action_proposal` authorization.
- A repair attempt requires separate `repair_proposal` authorization.
- Provider, model, adapter version, run, task, trace, task kind/effect/input, and timeout are
  bound by trusted code. The model cannot choose or change them.
- At most one repair call is permitted, and invalid output is never reflected into that call.

## Output contract

The response is one bounded JSON object with exact fields: schema version, title, summary,
one or more heading/content sections, evidence notes, and unresolved questions. Duplicate
keys, non-finite values, unknown fields, tool-call fields, secret-like material, empty text,
oversized values, provider failure, and incomplete output fail closed.

The validated value receives a deterministic canonical SHA-256 digest. That digest is not
runtime evidence and cannot complete a task. A later separately specified composition must
transform validated content into a typed-tool input, pass policy and approval, execute inside
the workspace sandbox, and append outcome evidence before any success transition.

## Non-goals

Phase 4A does not compose live task execution, read workspace inputs, select a tool, open a
network connection, run shell commands, install packages, write or delete files, publish,
deploy, contact external users, promote capabilities, or establish production qualification.
