# ADR 0009: Capital planning as the first commercial RAD Operations workflow

Status: Accepted

## Context

Phase 6 requires one coherent vertical workflow. The installed engines do not yet share an
honestly qualified cross-domain contract: PathWoven is qualified only for five packaged benchmark
objectives and vQPU only for local CPU quantum simulation. Forcing either into a financial
allocation would create misleading evidence.

## Decision

The first vertical is **RAD Capital Planning**, a non-executing portfolio-allocation review. It
ingests one bounded, current, operator-supplied JSON snapshot; binds it to a reproducible plan;
requires one-use human approval of the exact digest; routes the qualified Financial Algorithm
through RAD Node; compares the recommendation with the current allocation; verifies feasibility
and denied execution authority; and exports a tamper-evident dossier.

The product does not connect to brokers, place orders, retrieve live market data, or claim future
performance. PathWoven and vQPU remain independently available RAD capabilities but are not used
by this workflow until domain-specific contracts and benchmarks qualify their participation.

## Consequences

This ships a defensible commercial kernel without architectural theatre. Production validation
with real organizations, live governed connectors, tenant isolation, and external-action
integration remain separate qualifications. GPU, HPC, cloud, and physical QPU routing remain
Phase 7.
