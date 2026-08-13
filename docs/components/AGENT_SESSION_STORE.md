# Component AQ: Durable Agent Session Store

The Phase AQ store is the transactional boundary for Agent sessions and candidate
revisions. It validates and recomputes candidate digests, applies optimistic sequence
control, preserves append-only history, and binds approval to an exact candidate digest
and an externally established human principal.

SQLite WAL and full-synchronous writes provide the initial single-process durability
boundary. Authentication, inference, runtime dispatch, and HTTP/UI composition remain
separate later components.
