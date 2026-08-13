# Component AI: Local OpenAI-Compatible Adapter

Status: SPECIFIED | Live status: UNVERIFIED | Boundary contract: 1.0

The adapter maps bounded NEXUS reasoning tasks to the OpenAI-compatible Chat
Completions shape used by local inference servers. It accepts only an explicit
loopback base URL, model identifier, injected transport, and optional opaque secret
reference. No ambient credential or endpoint discovery is permitted.

Only validated chat messages enter the request. Arbitrary provider-task metadata,
secret-like fields, tools, approval decisions, and execution directives are not
forwarded. Responses must contain a bounded identifier, exactly one assistant text
choice, an accepted terminal reason, and non-negative token usage. Output text is
redacted before it crosses the provider-neutral result boundary.

The adapter is synchronous and truthfully advertises no resume capability. Terminal
cancellation is idempotent; nonterminal transport cancellation is not claimed. A
connected local model remains unqualified until the separate model-qualification
contract has sufficient evidence.

Unit, security, integration, and conformance tests use an injected fake transport.
They do not install a model runner, download weights, open a socket, prove a particular
server's compatibility, assess model quality, or authorize network access.
