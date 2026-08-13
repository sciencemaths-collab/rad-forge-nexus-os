# Local Model Evaluation Runbook

## Preconditions

Start an OpenAI-compatible server separately and confirm which model it exposes. Do
not expose the server beyond loopback. Copy the trusted digest from
`benchmarks/model-evaluation/reference-v1.sha256`; do not calculate a new anchor after
changing the corpus and treat it as independent evidence.

## Run the public reference evaluation

```bash
uv run nexus-model-eval \
  --base-url http://127.0.0.1:11434/v1 \
  --model YOUR_LOCAL_MODEL_ID \
  --corpus benchmarks/model-evaluation/reference-v1.json \
  --corpus-digest sha256:b9fa09369641225025b78ef3bb73759443b8d9e22e532af7757fffd8c6c55972 \
  --output local-evaluation.json \
  --run-id 40000000-0000-4000-8000-000000000001 \
  --trace-id 44444444444444444444444444444444 \
  --evaluated-at 2026-08-13T16:00:00Z \
  --authorize-loopback
```

If the server requires a key, place it in an operator-controlled environment variable
and add `--credential-ref env:VARIABLE_NAME`. The manifest will contain neither the
variable name nor its resolved value.

## Interpret the result

`PASS`, `LIMITED`, and `FAIL` are category evaluation outcomes. The manifest remains
`NOT_QUALIFIED` regardless of scores. An independent evidence process must verify the
run, anchor evidence UUIDs, and pass them through Component AJ before any Agent use is
allowed. Never rename a passing evaluation manifest as qualification evidence or use
it to bypass NEXUS OS policy and approval.
