# Component AM Evidence: Reference Reasoning Model Benchmark Corpus

Date: 2026-08-13 | Outcome: CLEAN-ROOM QUALIFIED (PUBLIC REFERENCE CORPUS)

Implemented and focused-test verified:

- Fourteen provider-neutral cases with exactly two cases in each required category
- Software, research, evidence, policy, approval, adversarial, and repair scenarios
- Public Draft 2020-12 suite schema and strict unknown-field rejection
- Canonical order-independent corpus digest with separate trusted SHA-256 anchor
- Bounded UTF-8 loading with duplicate-key and non-finite JSON rejection
- Minimum category-depth, unique identifier, secret-like prompt, size, and tamper checks
- Exact rubric execution through the Phase AK runner with raw prompt/output exclusion
- Focused unit, contract, integration, security, and failure suite: 8 passed

- Clean-room snapshot manifest and regression contract include benchmark sources
- Full Python suite: 347 passed; TypeScript suite: 6 passed
- Ruff formatting/lint, strict mypy, schemas, online/offline Python builds, and
  TypeScript packaging passed
- Portable Python and npm dependency audits passed with no known third-party
  vulnerabilities
- All 15 release gates and isolated independent review passed with zero findings

No live model was called or scored. The public exact-match corpus is a reproducible
baseline, not a hidden or production-complete certification set. Owner approval and
production release remain pending.
