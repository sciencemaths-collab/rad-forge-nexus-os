# Local Model Evaluation Command

Status: Accepted Phase AN boundary | Normative

## Purpose

`rad-model-eval` is the operator-facing composition of the Phase AL loopback
transport, Phase AI local adapter, Phase AM reference corpus, and Phase AK controlled
runner. It evaluates one explicitly identified local model and writes a tamper-evident
manifest for later independent evidence review. It does not qualify the model.

## Required operator inputs

The command requires an explicit loopback `/v1` endpoint, model identifier, corpus
path, trusted corpus SHA-256 digest, new output path, run UUID, 32-character trace ID,
UTC evaluation timestamp, and `--authorize-loopback`. An optional credential must be
an explicit `env:VARIABLE` reference; literal credentials and unsupported backends are
rejected.

No endpoint, model, corpus, timestamp, identity, credential name, or network grant is
discovered from ambient configuration. Supplying the authorization flag grants only
the endpoint's pinned loopback host and declared port for that invocation.

## Output contract

The output is created with exclusive, no-follow semantics, mode `0600`, flush, and
filesystem synchronization. Existing files, symlinks, missing parents, and unsafe
paths are rejected rather than overwritten. The manifest binds:

- run and trace identity;
- provider, adapter version, and model identity;
- SHA-256 of the endpoint rather than the endpoint itself;
- complete raw-output-free Phase AK report;
- canonical manifest SHA-256; and
- fixed `NOT_QUALIFIED` state.

It excludes credentials, credential references, raw prompts, raw model responses,
evidence UUIDs, approval claims, and qualification claims. Case failures are valid
evaluation outcomes and do not falsely turn the model into a qualified provider.

## Phase AN non-goals

Phase AN does not start a server, discover or download models, resolve vault backends,
stream output, retry failed cases, create trusted evidence, qualify a model, choose a
model for the user, or run a live server during automated tests.
