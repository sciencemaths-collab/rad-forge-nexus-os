# Component M: Tamper-Evident Evidence Ledger

Status: TESTED | Boundary contract: 1.0

`EvidenceLedger` durably appends schema-aligned evidence metadata to SQLite. Each
record binds canonical metadata and input/output digests to the previous record
with SHA-256. Appends use an expected-head comparison inside an immediate
transaction. Stable per-run sequence metadata and unique constraints prevent gaps,
duplicates, forks, and reordering. Database triggers reject update and delete.

`verify_chain` recomputes every record hash, validates scope, sequence, identifiers,
and links, and optionally checks a separately trusted record-count/head anchor.
Those anchors are required to prove that the final tail was not removed from an
export. The ledger stores no arbitrary payloads or resolved secrets.

This component does not provide signatures, remote timestamping, replicated/WORM
storage, key management, or qualification decisions. A database owner can replace
the entire database and its triggers; external anchoring and deployment controls
remain later security and release gates.
