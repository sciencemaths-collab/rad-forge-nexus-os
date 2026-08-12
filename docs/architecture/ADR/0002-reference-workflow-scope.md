# ADR-0002: Reference Workflow Scope

Status: Accepted | Date: 2026-08-11

## Context

The owner directive requires a runtime proof that imports and analyzes 100,000 CSV
rows, persists state, and emits evidence. The longer formal PDF also describes a
spreadsheet UI workflow with a virtual grid and render performance target.

## Decision

Define `RW-100K` as the kernel/data-analysis acceptance workflow. Track the virtual
grid edit/filter/sort/join/pivot/chart workflow as a separate spreadsheet
capability qualification that depends on, but is not satisfied by, `RW-100K`.

## Consequences

The runtime can be qualified independently without falsely claiming the UI exists.
Later UI acceptance receives its own hardware profile, benchmarks, and evidence.

