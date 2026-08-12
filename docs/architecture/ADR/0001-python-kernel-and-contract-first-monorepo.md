# ADR-0001: Python Kernel and Contract-First Monorepo

Status: Accepted | Date: 2026-08-11

## Context

The starting workspace contains only the formal specification PDF, with Python
3.12/uv and Node.js available. NEXUS needs strong schema, data, API, CLI, testing,
and provider integration support while keeping vendor code outside the kernel.

## Decision

Use a Python 3.12 kernel packaged with `uv`, strict type checking, JSON Schema
Draft 2020-12, an OpenAPI control contract, and a thin TypeScript SDK. Begin as a
modular monorepo and single deployable process. Use SQLite behind ports initially.
Do not distribute services until state, idempotency, and recovery semantics pass.

## Consequences

This minimizes premature operational complexity and supports analytical/research
work. Python performance-sensitive operations must use streaming/vectorized/native
libraries behind deterministic interfaces. Vendor SDKs remain adapter-only. A
future language/service split must preserve contracts and be justified by evidence.

