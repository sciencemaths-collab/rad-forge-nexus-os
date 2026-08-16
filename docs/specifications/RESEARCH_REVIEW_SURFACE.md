# Research Review Surface

Status: Draft implementation baseline

## Purpose

RAD Agent must make the governance and evidence controls of an approved `research` candidate
visible to the operator before execution. The browser supplements, but never replaces, review
of the complete immutable candidate and its digest. Research mode is domain-neutral and may be
used for scientific, technical, legal, policy, market, or other evidence-driven work.

## Required presentation

For a candidate whose mode is `research`, the browser displays:

1. the exact research objective;
2. source locator, retrieval, digest, access, extraction, and cited-span obligations;
3. claim links and the separation of direct, calculated, and inferred statements;
4. deterministic-computation provenance and the prohibition on authoritative model numbers;
5. contradiction retention, unresolved conflicts, uncertainty, and limitations;
6. citation and reproducibility verification requirements;
7. sensitive or regulated-data controls and external-action boundaries;
8. every acceptance criterion and the candidate's highest governed effect and risk reasons.

For other candidate modes, the research dossier remains hidden. All model-originated values
are inserted through text-only DOM operations. The interface must not use this summary to
claim research validity, approval, verification, publication readiness, or production
qualification.

## Acceptance

- Static transport tests establish that the research controls ship in the served assets.
- A packaged, qualified-provider browser journey returns a domain-neutral `research` candidate
  and verifies the dossier, acceptance identifier, risk effect, and external-action warning.
- The same journey continues through governed execution, evidence verification, and verified
  artifact download without a separate research execution bypass.
