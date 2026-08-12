# Provider Model

Providers are replaceable executors behind the stable AgentAdapter contract. The
kernel knows normalized tasks, events, results, failures, usage, and capabilities;
it does not import or expose vendor SDK types.

Capability discovery is descriptive, not trusted. Selection intersects task needs,
data policy, workspace/network permissions, model/provider capability evidence,
cost/time bounds, health, and configured role. Fallback must preserve data policy
and semantics and is recorded as a new attempt.

Initial adapters are Codex/OpenAI coding, Claude/Anthropic, OpenAI general model/
agent, and local/mock. The mock adapter is the normative deterministic reference.
Live adapters may be implemented without credentials but remain unverified until
opt-in conformance tests pass. Provider-specific resume or streaming features are
represented as capabilities and degrade explicitly when unsupported.

Adapters must redact credentials, isolate workspaces, validate all provider output,
map errors into the shared taxonomy, honor cancellation/timeouts, propagate traces,
and expose usage without claiming authoritative billing totals.

