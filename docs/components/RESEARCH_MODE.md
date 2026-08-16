# Component AC: Research Mode Pack

Status: TESTED | Boundary contract: 1.0

`ResearchMode` compiles a validated `research` project into the shared kernel graph:
protocol, source acquisition, extraction, claim construction, deterministic computation,
synthesis, conflict review, citation verification, reproducibility, and evidence reporting.
It does not fork the runtime or bypass policy, approval, sandbox, evidence, or qualification.

The graph requires source locator/time/digest/access/extractor provenance; claim links to
source spans or deterministic artifacts; direct/calculated/inferred derivation labels;
computation engine/version/parameters/environment/seed/digests/reproducibility; retained
contradictions; deterministic citation and value checks; explicit limitations; and final
acceptance evidence. Provider and secret configuration are excluded from task inputs.

The synthesis stage is explicitly non-publishing, and no external communication task is
emitted. This compiler does not acquire sources, classify sensitive data, execute research,
judge scientific quality, or authorize egress. Those operations must still pass the shared
runtime controls, and publication or messaging always requires a separately policy-gated
action and human approval.

## Operator review surface

When a qualified candidate selects `research` mode, the browser presents a scientific review
dossier before approval. It separates the biological question, source-provenance obligations,
claim and deterministic-computation grounding, contradictory evidence, citation and
reproducibility gates, sensitive-data controls, publication boundaries, acceptance criteria,
and the proposed risk effect. The dossier is derived from the immutable candidate and uses
text-only DOM assignment for model-originated content. It does not infer scientific validity
or replace review of the complete digest-bound candidate.

## Local source ingestion

The bundled qualified runtime binds `mode.research.source_acquisition` to
`research.ingest_local_sources`. An operator supplies bounded UTF-8 `.txt` or `.md` sources
and a strict provenance manifest under the approved workspace's `research-sources/` directory.
The tool performs no network access, rejects unsafe paths, symlinks, secret-like content, and
oversized inputs, then writes a deterministic `sources.json` artifact containing normalized
text and digest-bound provenance. Later research stages remain separately governed and do not
gain authority to fetch, publish, or declare scientific validity.
