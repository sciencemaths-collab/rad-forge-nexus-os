# Component AN Evidence: Local Model Evaluation Command

Date: 2026-08-13 | Outcome: CLEAN-ROOM QUALIFIED (INJECTED TRANSPORTS)

Implemented and focused-test verified:

- Installed `nexus-model-eval` operator entry point
- Explicit endpoint, model, corpus/digest, output, run/trace identity, UTC time, and
  loopback authorization inputs
- Optional explicit environment credential reference with no serialized reference/value
- Full AL → AI → AM → AK composition through injected standard-library connections
- Public Draft 2020-12 manifest schema and canonical manifest digest
- Endpoint digest and raw prompt/response exclusion
- Exclusive no-follow `0600` output, flush, synchronization, and no overwrite
- Remote endpoint, missing authorization, non-UTC time, literal/unsupported credential,
  existing file, symlink, and provider exception safety checks
- Truthful `NOT_QUALIFIED` output for passing and failing evaluation reports
- Focused unit, contract, integration, security, and failure suite: 9 passed

- Full Python suite: 356 passed; TypeScript suite: 6 passed
- Ruff formatting/lint, strict mypy, schemas, online/offline Python builds, and
  TypeScript packaging passed
- Portable Python and npm dependency audits passed with no known third-party
  vulnerabilities
- All 15 release gates and isolated independent review passed with zero findings

No live server or model was called, installed, scored, or qualified. Owner approval
and production release remain pending.
