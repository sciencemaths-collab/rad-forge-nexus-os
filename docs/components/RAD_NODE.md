# Phase 2: RAD Node

Status: TESTED | Boundary contract: 1.0

RAD Node is a durable, integrity-verified, bounded local execution host for Capability Protocol
implementations. It preserves native RAD governance by routing through exact qualification and
delegating execution to bound implementations. Registration, discovery, lifecycle, leases,
crash abandonment, authentication scopes, and health are explicit and fail closed.

The complete local suite passes with 582 tests and two intentionally opt-in live-cloud tests
skipped. No federation, remote network exposure, engine-specific qualification, or production
promotion is claimed by this component.
