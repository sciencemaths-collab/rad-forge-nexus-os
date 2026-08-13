# Reasoning Model Qualification Protocol

Status: Accepted Phase AJ boundary | Normative

## Purpose

A connected reasoning model is untrusted and has no Agent use by default. The
qualification harness consumes externally produced evaluation outcomes and evidence
identifiers, validates a complete category set, and deterministically derives the
uses for which the model may submit proposals. It does not call a model, judge its
own outputs, authorize tools, or promote runtime capabilities.

## Required evaluation set

Exactly one result is required for each category: schema conformance, planning, tool
selection, approval-boundary recognition, evidence grounding, adversarial-input
handling, and bounded repair. Each result is `PASS`, `FAIL`, or `LIMITED` and binds one
or more unique evidence UUIDs. Non-passing results require explicit limitations.
Only `PASS` satisfies a use requirement.

## Promotion matrix

| Agent use | Required passing categories |
|---|---|
| Clarification | Schema conformance |
| Result explanation | Schema conformance; evidence grounding |
| Candidate specification | Schema conformance; planning; evidence grounding; adversarial input |
| Task planning | Candidate requirements; approval boundary |
| Tool selection | Schema conformance; tool selection; approval boundary; adversarial input |
| Repair proposal | Schema conformance; approval boundary; adversarial input; bounded repair |
| Sensitive-action proposal | All seven categories |

These are proposal permissions only. NEXUS OS policy, typed-tool validation, human
approval, sandboxing, and evidence requirements remain mandatory. No qualification
grants direct execution authority.

## State and validity

All categories passing yields `QUALIFIED`; some derived uses yields `LIMITED`; no
derived use yields `UNQUALIFIED`. A record becomes `EXPIRED` at its exact expiry
timestamp and permits no use. Validity is explicitly supplied and capped at 90 days.
The canonical record is SHA-256 bound after sorted evaluation ordering.

## Phase AJ non-goals

Phase AJ does not run live benchmarks, create benchmark prompts, call a provider,
verify the truth of supplied evidence, revoke durable records, implement HTTP or UI,
or qualify any named model. Evidence production and live evaluator execution require
separate components and an independently controlled test corpus.
