# Component BD — RAD Capital Planning

Status: implemented and locally verified in Phase 6.

## Evidence classes

- Contract tests fix the plan fields, engine binding, acceptance set, and deterministic digest.
- Unit tests cover current-source ingestion, dimensions, bounds, duplicate keys, source identity,
  and covariance validity.
- Integration tests use the installed Financial Algorithm through its real RAD adapter and RAD
  Node, consume an exact approval, verify the baseline comparison, and download the complete
  evidence bundle.
- Security and failure tests reject altered plans, extra secret-bearing fields, and missing
  approvals without engine execution or evidence claims.

The engine evidence is deterministic real-engine evidence, not fake-provider or LLM evidence.
The model benchmark is reported independently because a reachable model is not necessarily a
qualified model.

## Qualification boundary

Automated evidence qualifies the local recommendation workflow for the packaged contract. It does
not qualify live market ingestion, source authenticity, investment performance, transactions,
multi-tenant production, or customer outcomes. The dossier always denies execution authority.
