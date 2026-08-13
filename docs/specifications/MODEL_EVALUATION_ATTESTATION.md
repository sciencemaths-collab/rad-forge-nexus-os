# Model Evaluation Attestation and Qualification Promotion

Status: Accepted Phase AO boundary | Normative

## Purpose

Phase AO is the trust bridge from a Phase AN `NOT_QUALIFIED` evaluation manifest to a
Phase AJ evidence-derived model qualification. It verifies independently produced
evidence; it does not create evidence, rerun the model, rescore cases, or grant runtime
authority.

## Manifest verification

The manifest and nested report must contain exactly the public contract fields. Their
canonical SHA-256 digests are recomputed before evidence is considered. The manifest
must remain `NOT_QUALIFIED`, contain all seven category outcomes, and carry valid run,
trace, provider, model, adapter, timestamp, corpus, endpoint, report, and manifest
identities.

## Evidence requirements

Promotion requires exactly seven sealed records in one append-only chain and trusted
external anchors for both record count and chain head. Each category has exactly one
record with:

- kind `BENCHMARK` and evidence outcome `PASS` (the attestation process passed);
- `input_digest` equal to the evaluation manifest digest;
- `output_digest` equal to the evaluation report digest;
- the same run UUID and trace ID as the manifest;
- a producer on the explicit trusted-producer allowlist;
- a timestamp from evaluation time through attestation time; and
- `test_id` equal to `model-evaluation:<category>:<observed-result>`.

The evidence outcome describes successful independent attestation. The category result
remains the observed `PASS`, `LIMITED`, or `FAIL`; attestation cannot improve it.

## Promotion result

After verification, Phase AO creates one Phase AJ `ModelEvaluation` per category using
only the corresponding ledger evidence UUID. Phase AJ deterministically derives Agent
proposal uses and expiry. The attested wrapper binds the manifest digest, evidence
count/head, attestation time, producer set, qualification object, and canonical
attestation digest.

Model permissions remain proposal permissions. NEXUS OS policy, typed tools, sandbox,
approval, execution evidence, and production qualification are unaffected.

## Phase AO non-goals

Phase AO does not decide who should be trusted, create attestations, accept self-signed
model claims, persist qualifications, implement revocation, run a live model, or grant
production status.
