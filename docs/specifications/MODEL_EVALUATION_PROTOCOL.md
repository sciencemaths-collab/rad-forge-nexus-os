# Controlled Reasoning Model Evaluation Protocol

Status: Accepted Phase AK boundary | Normative

## Purpose

The controlled runner evaluates a connected reasoning provider against a fixed,
versioned structured-output corpus. It produces auditable observations for the Phase
AJ qualification harness without granting the provider tools, approvals, execution
authority, or the ability to declare its own result.

## Corpus contract

A suite contains 7–256 uniquely identified cases and covers all seven qualification
categories. Every case contains a bounded, secret-free prompt, an exact canonical
JSON object rubric, and a timeout from 1–300 seconds. The canonical sorted corpus is
SHA-256 bound. Test case ordering cannot alter the digest or outcome.

Exact JSON matching is deliberately conservative for this first runner. Duplicate
keys, unknown fields, malformed JSON, non-finite values, provider failures, identity
mismatches, missing or oversized output, and timeouts fail the case.

## Execution and observation

Cases are submitted sequentially through the provider-neutral `AgentAdapter` using
the `reasoning_evaluation` operation. The provider receives only the system boundary
and case prompt. It receives no tools, evidence identifiers, qualification state,
approval records, arbitrary task metadata, or secrets.

Reports retain case identity, category, pass/fail status, output SHA-256 digest, and a
bounded failure code. Raw prompts and raw model outputs are excluded. All cases
passing yields category `PASS`; a mixed category yields `LIMITED`; zero passing yields
`FAIL`.

## Evidence boundary

The runner cannot create trusted evidence. An independent evidence service must bind
one unique ledger evidence UUID to each category before the report can become Phase
AJ `ModelEvaluation` input. The final model qualification remains deterministic and
does not bypass RAD Agent policy or approval.

## Phase AK non-goals

Phase AK does not ship a benchmark corpus for a named model, judge open-ended prose,
compare model quality, run a live provider in CI, install weights, implement a network
transport, persist evidence, or qualify a model for production.

The source-controlled Phase AM `reference-v1` corpus is the first conforming public
suite. Its public and exact-match limitations are defined in
`REFERENCE_MODEL_BENCHMARK_CORPUS.md`.
