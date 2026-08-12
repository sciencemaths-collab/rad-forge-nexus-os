# Component Q: Deterministic Mock Provider

Status: TESTED | Boundary contract: 1.0

The mock implements the provider-neutral `AgentAdapter` port using bounded,
operation-selected scenarios. It emits fixed UTC, contiguous-sequence events and
normalized terminal results without clocks, randomness, network, filesystem, vendor
SDKs, or credentials. Scenarios cover successful completion, pending execution,
typed provider failure, idempotent cancellation, and capability-gated resume.

Task identifiers are unique within an adapter instance. Unknown tasks, duplicate
dispatch, unconfigured strict operations, premature result reads, and unsupported
resume fail with safe normalized errors. Inputs and scripted metadata pass through
the Component P/K redaction boundary before they can appear in events or results.

This component is a deterministic test adapter, not the complete conformance harness
and not evidence that any live provider works. Timeout enforcement, malformed live
payload probes, policy/sandbox integration, and provider-version qualification remain
Components R–T and later integration gates.
