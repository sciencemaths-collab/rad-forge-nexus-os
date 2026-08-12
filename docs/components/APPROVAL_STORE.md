# Component J: Durable Approval Store

Status: TESTED | Record contract: 1.0

The SQLite-backed approval store persists explicit human decisions and atomically
authorizes only an approved, unexpired record matching the exact project, run, and
action digest. Successful authorization consumes the approval, preventing replay.
Denial, revocation, expiry, scope mismatch, duplicate IDs, and illegal transitions
fail closed.

This component does not provide an approval UI or actor authentication. Those
application and identity boundaries must call this store with authenticated
principals and remain later integration gates.
