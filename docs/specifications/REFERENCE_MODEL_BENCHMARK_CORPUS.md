# Reference Reasoning Model Benchmark Corpus

Status: Accepted Phase AM boundary | Normative

## Purpose

The reference corpus supplies independently authored, provider-neutral cases for the
Phase AK controlled runner. It tests the seven Phase AJ qualification categories
without allowing the evaluated model to choose the questions, expected answers,
scores, evidence identifiers, or qualification state.

## Corpus requirements

- JSON must satisfy `model-evaluation-suite.schema.json` and contain no unknown fields.
- A suite contains 14–256 cases and at least two cases per required category.
- Case identifiers are unique and prompts, expected outputs, and timeouts are bounded.
- Prompts and rubrics contain no credentials or opaque secret references.
- The canonical sorted suite digest must match a separately stored trusted SHA-256
  anchor before any case can run.
- Duplicate JSON keys, non-finite values, invalid UTF-8, oversized files, missing
  categories, shallow category coverage, and digest mismatch fail closed.

## Reference-v1 coverage

`reference-v1` contains two cases in each category:

| Category | Covered decisions |
|---|---|
| Schema conformance | Exact fields; typed values |
| Planning | Missing acceptance criteria; ordered governed workflow |
| Tool selection | Deterministic hashing; read-before-write effects |
| Approval boundary | Permanent deletion; public publication |
| Evidence grounding | Scientific claims; test-completion claims |
| Adversarial input | Policy override in retrieved text; credential disclosure request |
| Bounded repair | Attempt ceiling; unchanged repeated failure |

Expected outputs are exact JSON objects so scoring is deterministic and reviewer
reproducible. The corpus mixes software-engineering, research, data/evidence, and
security situations rather than optimizing for one model vendor or interface.

## Independence and limitations

The corpus is independent of the evaluated provider and model and is committed before
any live score. It is public, small, and exact-match; therefore it is a transparent
reference baseline, not a hidden or statistically comprehensive certification exam.
A model may be tuned against it. Production qualification requires controlled variants,
version rotation, leakage review, domain-expert review, and broader open-ended and
statistical evaluation. Corpus component qualification does not qualify a model.

## Phase AM non-goals

Phase AM does not call a live model, rank models, set hardware requirements, download
weights, introduce subjective LLM-as-judge scoring, create hidden test data, or grant
production status.
