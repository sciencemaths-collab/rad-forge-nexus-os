# Component D: Task Graph Compiler

Status: TESTED | Contract version: 1.0

The compiler converts an untrusted JSON-compatible task-graph payload into the
immutable provider-neutral domain graph. It validates Draft 2020-12 structure and
formats, rejects unknown fields and non-canonical values, enforces a 4 MiB input
bound, applies the optional acceptance-list default, and emits a stable digest.

Dependency existence, cycle detection, and scheduling order belong to Component E
and are deliberately not performed here. The schema is packaged so installed
wheels behave like source checkouts.
