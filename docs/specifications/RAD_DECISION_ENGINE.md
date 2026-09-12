# RAD Decision Engine 1.0

Financial Algorithm 0.2.0 is the first implementation, bound through adapter 1.0.0 as
`rad.decision.financial`. It exposes `portfolio.allocate`, `valuation.estimate`, and
`market.assess`. The capability accepts bounded numeric data only and has no transaction,
broker, account, credential, or network operation.

Every result is content-addressed, identifies the exact engine and adapter, declares limitations,
and sets `execution_authorized` to false. The RAD manifest independently requires both exact
capability qualification and approval, denies network access, and limits execution to 300 seconds
and 4,096 MiB. Approval authorizes generation of a decision artifact; it never authorizes an
external financial action.

Adapter construction requires the complete formal 25-case report. RAD canonicalizes the report,
recomputes its digest, and requires the release-pinned digest
`sha256:07cfa239eb43b657c87df2662db5861dfbb63557159ef0cf00d766eea40188dc`, exact identities,
all expected cases, deterministic replay, passing outcomes, and denied execution authority.

The engine's existing portfolio algorithm remains internal to the qualified financial domain
implementation. RAD may separately orchestrate the Phase 3 PathWoven capability for its qualified
built-in objectives. Financial delegation to PathWoven is prohibited until a portfolio-specific
PathWoven data contract and benchmark are independently qualified; arbitrary executable objective
injection will not be used as a shortcut.
