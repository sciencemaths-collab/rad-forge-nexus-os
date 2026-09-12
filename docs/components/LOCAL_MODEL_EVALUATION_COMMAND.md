# Component AN: Model Evaluation Command

Status: TESTED | Live status: OLLAMA EVALUATED, NOT QUALIFIED | Boundary contract: 1.0

Component AN provides the installed `rad-model-eval` entry point and a public
evaluation manifest schema. It supports loopback OpenAI-compatible models and an
explicit opt-in route through the official OpenAI cloud adapter. It composes already
qualified boundaries rather than adding model authority.

Operator intent is explicit and reproducible: network authorization, endpoint, model,
corpus digest, time, run identity, trace identity, and output destination are required.
The command writes a new private manifest atomically and returns stable machine-readable
exit codes and summaries. Provider exception text and resolved credentials are never
reported.

The cloud route requires `--authorize-cloud`, an opaque credential reference, and the
fixed official HTTPS endpoint. It cannot be combined with loopback authorization.
Automated tests inject scripted transports and make no live model quality claim.
