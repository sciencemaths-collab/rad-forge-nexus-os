# Observability

OpenTelemetry is the implementation standard, accessed through internal ports so
the kernel remains testable without an exporter. Traces link API request, planning,
run, task attempt, provider/tool call, approval wait, verification, evidence append,
and qualification decision.

Required attributes include project/run/task/attempt IDs, operation, state,
provider adapter and version, tool ID, effect class, outcome, failure class,
duration, retry count, and evidence ID. Attributes must not contain prompts,
credentials, raw user data, or unrestricted provider payloads. High-cardinality
payloads become protected artifacts referenced by digest.

Metrics cover queue/step latency, active/waiting runs, retries, failures by class,
approval duration, checkpoint recovery, provider health, usage/cost estimates,
evidence verification, and qualification/degradation. Logs are structured,
correlated, redacted, and bounded. Export failure must not corrupt runtime state;
buffering and loss are surfaced as health/evidence limitations.

