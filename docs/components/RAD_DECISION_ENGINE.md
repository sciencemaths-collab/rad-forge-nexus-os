# Phase 4: RAD Decision Engine

Status: TESTED | Boundary contract: 1.0

The first decision capability is Financial Algorithm 0.2.0 through adapter 1.0.0 and capability
ID `rad.decision.financial`. It produces review-only portfolio, valuation, and market-assessment
artifacts. Strict validation covers operation identity, dimensions, numeric finiteness, covariance
shape/symmetry/positive-semidefiniteness, compute budgets, request digests, result finiteness,
qualification integrity, and denied transaction authority.

Deterministic fixture tests prove RAD-side rejection behavior. Real-engine acceptance installs the
Financial Algorithm wheel and executes it through the adapter and RAD Node. The engine's formal
qualification covers 25 deterministic decision-support cases. No live market feed, broker,
account, order, profitability, suitability, or regulatory-compliance claim is made.
