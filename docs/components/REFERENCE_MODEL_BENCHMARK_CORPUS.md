# Component AM: Reference Reasoning Model Benchmark Corpus

Status: SPECIFIED | Live status: NOT RUN | Boundary contract: 1.0

Component AM adds the machine-readable `reference-v1` suite, its public JSON Schema,
trusted digest anchor, bounded loader, and corpus-specific contract/security tests.
The loader requires at least two cases in every Phase AJ category and rejects any
source change that does not match the independently supplied anchor.

The corpus is provider-neutral and contains no tool handles, credentials, approvals,
evidence UUIDs, model names, or vendor-specific response fields. Exact canonical JSON
rubrics make scoring deterministic through Phase AK.

The public corpus is a reference baseline. Hidden variants, leakage detection,
statistical reliability, expert content validation, and live model execution remain
separate qualification work.
