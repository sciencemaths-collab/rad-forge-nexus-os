# Local Research Source Ingestion

Status: Draft implementation baseline

## Purpose

The bundled research runtime needs one real, least-privilege domain tool. It ingests only
operator-supplied local text sources, preserves their declared origin and access context, and
produces a deterministic provenance artifact for later extraction, claims, and citations.

## Workspace contract

The approved workspace may contain `research-sources/manifest.json` and the declared `.txt`
or `.md` files below `research-sources/`. The strict manifest contains `schema_version: 1.0`
and one to 32 source objects with `path`, `locator`, UTC `retrieved_at`, and
`license_access` fields.

The tool accepts at most 512 KiB per source and 768 KiB total source bytes. Paths are relative,
traversal-free, and confined to the real source directory. Source directories, manifests,
files, and artifact targets must not be symlinks. Input must be UTF-8 text and secret-like
values are rejected rather than copied into an artifact.

## Output

`research.ingest_local_sources` writes `.rad-agent-artifacts/sources.json` atomically. The
artifact includes the manifest digest, raw-content and normalized-text digests, media type,
byte/character/line counts, stable source identifiers, normalized text, declared locator,
retrieval time, access note, and workspace-relative provenance. The source-set digest binds
the ordered records. Existing identical output is accepted; conflicting output is never
overwritten.

The tool has `WORKSPACE_WRITE` effect, no network capability, and is bound only to
`mode.research.source_acquisition`. This slice does not fetch literature, parse PDF/DOCX,
construct claims, judge source quality, contact external systems, or publish.
