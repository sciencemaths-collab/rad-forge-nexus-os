# Authenticated Task Preparation

Phase 4C exposes Phase 4B through the existing authenticated runtime application without adding an execution route.

`POST /v1/agent/sessions/{sessionId}/runtime/preparations` requires `agent:execute` and a durable idempotency key. The server selects an exact ready task (or validates the requested task), invokes the qualified reasoner only when no immutable binding exists, and returns the proposal with its canonical digest and explicit `PROPOSED` state.

The browser displays that artifact and digest before the exact governed action. Preview and execution then resolve the same stored binding through schema validation, policy, approval, the typed tool executor, and evidence recording. Reloading or replaying preparation recovers the stored artifact without a second model call.

The endpoint cannot select tools, approve effects, execute work, alter task definitions, or claim verification. Live-provider quality and production authorization remain separate qualification work.
