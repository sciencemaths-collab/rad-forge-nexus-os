# Component Z Evidence: TypeScript SDK

Date: 2026-08-12 | Outcome: TESTED

Qualification covers strict compilation and declarations, typed request/path/header
construction, request and trace identity, required mutation idempotency, immutable run
and collection parsing, structured safe API errors, malformed response and hostile
transport rejection, ambient secret/endpoint exclusion, and dry-run package contents.

Verified: 235 Python tests; 6 Node tests; strict TypeScript build; no runtime package
dependencies; npm package dry run; Ruff; strict mypy; schema/contracts; Python
sdist/wheel builds; and the existing offline fresh-installed-wheel smoke gate passed.
