# Component AS: Authenticated Agent Application API

Phase AS is a transport-neutral HTTP-shaped boundary. It authenticates through an
injected port, enforces exact scopes and human approval identity, validates OpenAPI
operations, composes the durable Agent store and reasoning controller, and persists
idempotent responses. It intentionally contains no socket server or execution endpoint.
