# Component AD: Data-Analysis Mode Pack

Status: TESTED | Boundary contract: 1.0

`DataAnalysisMode` compiles a validated `data_analysis` project into the shared kernel
graph: ingestion, schema inspection, data-quality checks, deterministic statistics,
chart-spec inputs, artifact-grounded explanation, persistence, reopen verification, and
evidence reporting. It does not fork or bypass runtime safety services.

Ingestion forbids model-generated authoritative numbers and records dataset identity and
shape. Schema, quality, statistics, chart, and reopen checks are deterministic single-
attempt gates. Only the prose explanation may use bounded retries, and all numeric claims
must reference verified artifact IDs; unverified numbers are explicitly prohibited. The
final evidence task is bound to every project acceptance identifier.

Provider bindings, credential/secret references, network policy, and cost settings are not
copied into task inputs. This component compiles analysis work only. It does not execute an
analysis, render charts, provide a virtual grid, prove 100K-row performance, or satisfy the
RW-100K workflow; those are Component AE integration and benchmark gates.
