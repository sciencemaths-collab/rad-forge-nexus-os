# Component P: Provider Adapter SDK

Status: TESTED | Boundary contract: 1.0

The SDK defines immutable normalized descriptors, capabilities, task requests,
sequenced events, usage estimates, terminal results, the async `AgentAdapter` port,
and a duplicate-safe registry. Descriptor serialization follows the provider schema;
credentials accept opaque secret references only. Provider task/event/result metadata
is recursively redacted before crossing the core boundary.

The core package imports no vendor SDK. This component does not implement a provider,
execute a task, enforce timeouts, or establish conformance. The deterministic mock,
conformance kit, and live adapters are Components Q–T.
