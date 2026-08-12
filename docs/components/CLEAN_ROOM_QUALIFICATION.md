# Component AG: Clean-Room Qualification

Status: QUALIFIED (OWNER APPROVAL PENDING) | Boundary contract: 1.0

The qualifier copies the declared release inputs into a disposable source snapshot, excluding
version-control metadata, dependency trees, caches, build products, and prior evidence. It
content-addresses that snapshot, forces fresh per-run Python and npm caches, installs locked
dependencies, and executes the complete Component AF release-evidence pipeline.

An independent deterministic review rejects placeholder or unimplemented production code,
dynamic execution, shell execution, vendor SDK imports in core packages, and drift from the
explicit non-production status. Findings contain only category, path, and line number.

A passing run writes JSON and Markdown reports bound to both the source snapshot and automated
evidence digests. Clean-room success does not authorize release: `owner_approved` and
`release_candidate` remain false until the owner approves the digest-bound release checklist.

