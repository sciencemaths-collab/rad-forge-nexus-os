# Component AE: RW-100K Reference Workflow

Status: TESTED | Acceptance contract: RW-100K

`ReferenceWorkflow` generates the fixed 100,000-row CSV fixture in deterministic code,
imports it through Component AA, verifies its exact row count and expected schema, emits
data-quality findings and summary statistics, creates a digest-linked chart specification,
and produces numeric explanation claims that each carry the statistics artifact ID.

The workflow atomically persists digest-anchored state and JSON/Markdown evidence reports.
A separately constructed workflow instance reopens the state, recomputes its state digest,
verifies the seven-record SQLite evidence chain against its trusted count/head anchor, and
rejects mutation or replay. The large CSV is generated during qualification and is not
committed to source control.

This is the runtime-only RW-100K scope frozen by ADR-0002 and `ACCEPTANCE_SPEC.md`. It does
not expose a virtual grid, browser rendering, scrolling/edit/filter/sort/join/pivot UI, or
claim sub-two-second first usable browser rendering. Those remain explicitly assigned to
the later spreadsheet product capability and are not silently counted as passing here.
