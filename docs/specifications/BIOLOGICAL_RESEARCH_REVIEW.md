# Biological Research Review Surface

Status: Draft implementation baseline

## Purpose

RAD Agent must make the scientific controls of an approved `research` candidate visible to
the operator before execution. The browser supplements, but never replaces, review of the
complete immutable candidate and its digest.

## Required presentation

For a candidate whose mode is `research`, the browser displays:

1. the exact research objective;
2. source locator, retrieval, digest, access, extraction, and cited-span obligations;
3. claim links and the separation of direct, calculated, and inferred statements;
4. deterministic-computation provenance and the prohibition on authoritative model numbers;
5. contradiction retention, unresolved conflicts, uncertainty, and limitations;
6. citation and reproducibility verification requirements;
7. sensitive biological or health-data controls and the external-publication boundary;
8. every acceptance criterion and the candidate's highest governed effect and risk reasons.

For other candidate modes, the research dossier remains hidden. All model-originated values
are inserted through text-only DOM operations. The interface must not use this summary to
claim scientific validity, approval, verification, publication readiness, or production
qualification.

## Acceptance

- Static transport tests establish that the research controls ship in the served assets.
- A packaged, qualified-provider browser journey returns a `research` candidate and verifies
  the dossier, acceptance identifier, risk effect, and non-publication warning before approval.
- The same journey continues through governed execution, evidence verification, and verified
  artifact download without a separate research execution bypass.

