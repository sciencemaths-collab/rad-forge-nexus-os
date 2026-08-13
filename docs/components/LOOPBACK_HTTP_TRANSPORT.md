# Component AL: Local OpenAI-Compatible Loopback HTTP Transport

Status: SPECIFIED | Live status: UNVERIFIED | Boundary contract: 1.0

This component is the concrete network implementation behind the Phase AI injected
transport protocol. It uses Python's standard HTTP client, no vendor SDK, and no
ambient endpoint or credential discovery.

An explicit sandbox grant is mandatory. `localhost` is pinned to IPv4 loopback, the
host and port are authorized before connection creation, redirects are absent, JSON
and content type are strict, sizes and timeouts are bounded, and every connection is
closed. Tests inject connection objects and therefore open no socket.

The transport makes a local model reachable; it does not qualify that model. Phase AK
evaluation and Phase AJ evidence-derived qualification remain separate gates.
