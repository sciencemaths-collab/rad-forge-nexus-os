# Component X: CLI Surface

Status: TESTED | Boundary contract: 1.0

The CLI is a thin async client of the control API port. It implements run
create/get/cancel/resume, provider and capability listing, and evidence verification.
Arguments are bounded and validated before any client call; mutations require explicit
idempotency keys. Output is canonical JSON, request/trace metadata remains at the client
boundary, and raw exceptions or credentials are never printed.

Stable exit classes distinguish success (0), validation (2), authorization/approval
(3), execution/API failure (4), evidence integrity failure (5), and internal/client
failure (70). Evidence verification returns nonzero when the response is not valid.

The reusable CLI executes through an injected client and passes integration against the
Component W application. The installed console entry point is present, but until the
Python SDK/client wiring in Component Y is configured it returns a machine-readable
`client_not_configured` error. It does not guess an endpoint, parse bearer credentials,
or embed an HTTP implementation.

