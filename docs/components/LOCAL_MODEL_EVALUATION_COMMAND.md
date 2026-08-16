# Component AN: Local Model Evaluation Command

Status: SPECIFIED | Live status: NOT RUN | Boundary contract: 1.0

Component AN provides the installed `rad-model-eval` entry point and a public local
evaluation manifest schema. It composes already qualified boundaries rather than
adding model authority.

Operator intent is explicit and reproducible: network authorization, endpoint, model,
corpus digest, time, run identity, trace identity, and output destination are required.
The command writes a new private manifest atomically and returns stable machine-readable
exit codes and summaries. Provider exception text and resolved credentials are never
reported.

Automated tests inject scripted and HTTP connection transports. They open no socket
and make no live model compatibility or quality claim.
