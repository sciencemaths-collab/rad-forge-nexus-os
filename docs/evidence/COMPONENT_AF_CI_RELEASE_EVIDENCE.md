# Component AF Evidence: CI and Release-Evidence Automation

Date: 2026-08-12 | Outcome: TESTED

Qualification covers frozen gate order, first-failure stopping, blocked evidence output,
secret-pattern detection without value disclosure, ignored build/dependency directories,
least-privilege workflow permissions, portable dependency audits, report/checklist/limitations
generation, build provenance, and a 36-component Python/npm lockfile-derived CycloneDX SBOM.

The updated real generator completed all 15 recorded gates and returned
`AUTOMATED_GATES_PASS`; it intentionally returned `release_candidate: false` because clean-
room qualification and owner approval remain pending.

Verified: 285 tests; repository-wide format check; Ruff; strict mypy; schema/contracts;
TypeScript tests; RW-100K; builds; secret scan; and the complete local evidence generator.
