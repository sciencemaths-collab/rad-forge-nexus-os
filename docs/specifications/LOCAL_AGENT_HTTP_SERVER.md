# Local Agent HTTP Server Specification

Status: frozen for Component AY

## Purpose

Component AY exposes the transport-neutral RAD Agent application through an
operator-run local HTTP process. It authenticates a human operator without
requiring a model-provider API key. Model selection and application composition
remain separate concerns.

## Contract

- `nexus-agent-serve` binds only an explicit IP loopback address and a bounded,
  non-privileged configured port.
- First start requires a regular bootstrap-password file that is readable only
  by its owner. The password is never accepted as a command-line value.
- The durable verifier uses a random salt and `scrypt`; neither plaintext
  passwords nor bearer tokens may be persisted.
- `POST /v1/auth/login` accepts one bounded JSON object and returns a random,
  short-lived bearer session. Authentication failures are generic and limited
  per client address.
- Session tokens are held only in process memory, expire within one day, and are
  invalid after restart or explicit revocation.
- `GET /healthz` and `GET /readyz` report process availability. All other
  requests are translated into `AgentApiRequest` and delegated without changing
  the existing authorization, approval, replay, or evidence semantics.
- Request bodies are at most 1 MiB, request identifiers are bounded printable
  values, and responses disable caching and MIME sniffing.
- Requests with a non-loopback Host header fail closed. The server emits no
  default access log that could capture credentials or tokens.
- Shutdown stops accepting work, closes the socket, clears in-memory sessions,
  and closes the authentication store.

## Exclusions

AY does not provide public-network exposure, TLS termination, multi-user identity,
browser CORS, a built-in model, or provider credentials. A local application
factory is explicitly selected by the operator; the supported model/configuration
experience is delivered by the following product stages.

## Acceptance gates

1. Password bootstrap, login, expiry bounds, session limits, revocation, and
   absence of plaintext-at-rest are unit tested.
2. Health, login, bearer use, Host rejection, body bounds, throttling, and clean
   shutdown run over a real loopback socket.
3. Non-loopback binds and unsafe password-file permissions fail before serving.
4. Full Python tests, Ruff, strict mypy, contract validation, package build, and
   installed entry-point help all pass.
