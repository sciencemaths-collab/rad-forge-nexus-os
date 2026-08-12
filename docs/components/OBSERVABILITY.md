# Component O: Provider-Neutral Observability

Status: TESTED | Boundary contract: 1.0

`Telemetry` creates immutable trace, structured-log, and metric events through an
internal exporter port. Events use bounded scalar attributes, deterministic trace
correlation, UTC timestamps, and explicit start/end lifecycle checks. Sensitive
keys, raw payload fields, prompts, user data, secret references, credential formats,
and configured exact canaries are redacted before an exporter receives an event.

Exporter failures never propagate into runtime state. They are counted and exposed
through a safe health snapshot without retaining exception text or provider data.
`InMemoryExporter` is a bounded deterministic test adapter, not a production queue.

This component does not install a vendor SDK, provide a durable telemetry buffer,
guarantee delivery, or claim an OpenTelemetry deployment integration. Production
export adapters, backpressure, sampling, resource attributes, and operational alert
policy remain later integration and release gates.
