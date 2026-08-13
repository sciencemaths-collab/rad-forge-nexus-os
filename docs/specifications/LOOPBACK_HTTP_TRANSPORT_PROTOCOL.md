# Local OpenAI-Compatible Loopback HTTP Transport Protocol

Status: Accepted Phase AL boundary | Normative

## Purpose

The transport connects the existing local OpenAI-compatible adapter to an explicitly
configured local inference server. It supports the common `/v1/models` health endpoint
and `/v1/chat/completions` request shape used by Ollama, LM Studio, llama.cpp, and
similar servers without importing any vendor SDK.

## Authorization and endpoint rules

Every request requires an injected `WorkspaceSandbox` whose network allowlist contains
the exact pinned loopback address and requested port. An empty allowlist denies access.
Only explicit `http` or `https` `/v1` endpoints on `127.0.0.1`, `::1`, or `localhost`
are accepted. `localhost` is pinned to `127.0.0.1` before authorization and connection.
Remote, wildcard, credential-bearing, query-bearing, fragment-bearing, and alternate
path endpoints are rejected. Redirects are never followed.

## HTTP boundary

- Health uses `GET /v1/models`; only HTTP 200 with JSON content is healthy.
- Completion uses `POST /v1/chat/completions` with canonical UTF-8 JSON.
- Optional credentials are sent only as a single `Authorization: Bearer` header after
  CR/LF rejection and remain scoped by the adapter's opaque-secret resolver.
- Requests are capped at 512,000 bytes and responses at 2,000,000 bytes.
- Timeouts are explicit integers from 1–300 seconds.
- Success responses require `application/json`, UTF-8, one top-level object, unique
  keys, and finite JSON values.
- Connections close on success and every failure path. Provider bodies and exception
  text never cross the normalized transport error boundary.

Standard-library HTTPS uses the platform's default certificate verification. The
transport does not weaken TLS or add a trust-all mode.

## Phase AL non-goals

Phase AL does not discover servers, start model processes, download weights, choose a
model, stream tokens, retry requests, follow redirects, expose remote inference, or
perform a live call during automated qualification.
