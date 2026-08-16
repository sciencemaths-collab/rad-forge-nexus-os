# Local Research Source Extraction

Status: implemented in Phase 5G.

## Outcome

RAD Agent converts the verified local `sources.json` artifact into deterministic,
line-addressable records. The contract is domain-neutral: it supports research in any field
and does not interpret, rank, or construct claims.

## Contract

`research.extract_source_lines` is bound only to `mode.research.source_extraction`. It reads
`.rad-agent-artifacts/sources.json` inside the approved real workspace and writes
`.rad-agent-artifacts/extractions.json` atomically. Each record preserves the source ID,
locator, extracted-text digest, one-based line number, exact line text, and line digest.

Before extraction, nested source provenance and the source-set digest are recomputed. The
output binds itself to the exact source artifact and source set, records a deterministic
extraction-set digest, and is capped at 1 MiB. Existing conflicting artifacts, symlinks,
malformed JSON, and tampered provenance fail closed.

## Boundary

This stage performs no network access, model inference, arbitrary file reads, claim creation,
domain-specific analysis, or external publication. Those remain separate governed stages.
