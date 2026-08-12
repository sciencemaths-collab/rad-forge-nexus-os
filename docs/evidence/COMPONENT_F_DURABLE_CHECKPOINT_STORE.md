# Component F Evidence: Durable Checkpoint Store

Date: 2026-08-12 | Outcome: TESTED

The gate covers atomic save/update, stale-writer rejection, close/reopen persistence,
resume compatibility, corrupt/untrusted data boundaries, payload limits, packaging,
and the full regression suite.

Verified: 85 tests, including forced writer-process termination and recovery;
Ruff; strict mypy; schema/contracts; sdist/wheel builds; and fresh-wheel durable
save/close/reopen/load smoke all passed.
