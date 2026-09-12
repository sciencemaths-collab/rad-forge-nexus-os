# ADR 0012: No-host-import WebAssembly plugin runtime

Status: accepted

## Decision

Executable RAD plugins use the `wasm-v1` ABI in a Wasmtime sandbox. Modules receive canonical
JSON through exported linear memory and return a bounded JSON object. They receive no WASI and
may import no host function. Runtime activation requires an enabled, integrity-valid signed
package, zero host permissions, one exact capability, and a canonical unexpired qualification
attestation bound to plugin, capability, version, runtime, and benchmark digest.

Execution is fuel-bounded, memory-bounded, input/output-bounded, and routed through the existing
RAD Node capability qualification boundary. Plugin installation or enablement alone never grants
execution.

## Consequences

The first executable plugin class cannot access files, networks, clocks, random devices,
environment variables, secrets, subprocesses, or external systems. Those capabilities require
future narrowly scoped host interfaces and separate security qualification. This restriction
makes deterministic computation plugins useful now without importing third-party Python into the
RAD process.
