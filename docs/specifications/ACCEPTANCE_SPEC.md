# Acceptance Specification

Status: Draft baseline | Normative

## Acceptance rules

File existence is never acceptance. Each criterion requires a test ID, immutable
artifact or output digest, environment identity, and a passing evidence record.
Skipped, flaky, or quarantined tests do not satisfy release gates. Mock, live, and
production provider qualifications are reported separately.

## Foundation gate F0

- Required specification, architecture, ADR, runbook, schema, OpenAPI, and MCP
  files exist and contain no unresolved normative contradiction.
- Every JSON schema passes Draft 2020-12 meta-validation.
- Valid examples pass and invalid fixtures fail for the expected reason.
- OpenAPI and MCP documents parse and reference existing schemas.
- Secret-like literal values are absent from committed fixtures and documentation.

## Kernel gates

- Invalid/unknown configuration is rejected before side effects.
- Cycles and unknown task dependencies are rejected deterministically.
- Illegal state transitions cannot be persisted.
- Checkpoint save/resume and kill/restart preserve exactly-once state semantics.
- Retry stops at configured attempt/time/budget bounds.
- Approval denial blocks the action; approval acceptance authorizes only the
  exact action digest and expires according to policy.
- Destructive actions, traversal, workspace escape, and secret canary leakage are
  blocked and evidenced.
- Malformed provider output is rejected; eligible fallback works deterministically.
- Evidence verification detects mutation, deletion, reordering, and broken links.
- Capability promotion without required verified evidence is rejected.

## Surface gates

The CLI and both SDK examples execute against the mock runtime. OpenAPI requests
and responses validate. MCP tools validate input/output and enforce effect policy.
A clean install from documented instructions succeeds without undeclared tools.

## Reference workflow RW-100K

Using a generated, digest-pinned 100,000-data-row CSV fixture:

1. import without loading model-generated numbers;
2. prove exact data-row count of 100,000;
3. infer and validate the expected schema;
4. emit deterministic data-quality findings and summary statistics;
5. generate a validated chart specification from computed artifacts;
6. generate an explanation whose numeric claims are traceable to those artifacts;
7. save state, terminate the process, reopen, and verify persistence;
8. verify the complete evidence chain and produce JSON/Markdown reports.

The larger spreadsheet capability later adds a virtual grid, sub-two-second first
usable render on declared hardware, edit/filter/sort/join/pivot/chart/save/reopen.
It is not silently treated as satisfied by the runtime-only RW-100K workflow.

## Release gate

A release candidate requires clean checkout/install, format, lint, typecheck,
schema, unit, contract, integration, security, resilience, e2e, benchmark,
reference-workflow, evidence integrity, secret scan, documentation behavior audit,
known-limitations report, and owner-approved checklist. Live tests are opt-in and
cannot run repository-controlled code with broadly scoped secrets.

## Definition of done

Done means every deliverable in the project directive is implemented, the required
tests pass from a clean environment, evidence verifies, limitations are explicit,
documentation matches behavior, and release qualification has been approved. It
does not mean every provider is production-qualified.

