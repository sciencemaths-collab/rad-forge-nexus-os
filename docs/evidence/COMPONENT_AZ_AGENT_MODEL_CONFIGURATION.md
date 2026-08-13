# Component AZ — Agent Model Configuration Evidence

Date: 2026-08-13

## Scope

This record covers bounded local model profiles, OpenAI-compatible model
discovery, opaque credential scoping, exact evidence-derived qualification, and
health-gated resolution.

## Security and failure coverage

- public or malformed endpoints, unknown profile types/fields, and unsafe YAML;
- literal credentials and redacted public configuration;
- zero, duplicate, excessive, malformed, and ambiguous discovery results;
- model availability without qualification and qualification without health;
- exact provider/model/adapter binding for candidate and repair uses;
- proof that configuration resolution never invokes inference.

## Qualification

- exact `scripts/release_evidence.py` pipeline — passed, including contracts,
  formatting, lint, strict typing, Python/TypeScript tests, audits, builds, and
  clean-room evidence;
- full Python suite — 454 passed;
- source distribution and wheel — built;
- fresh-environment wheel installation and configuration/discovery imports —
  passed.

AZ remains local and non-live: no external provider or real model was contacted
by qualification tests.
