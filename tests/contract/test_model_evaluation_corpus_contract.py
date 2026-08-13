import json
from pathlib import Path

from jsonschema import Draft202012Validator


def test_reference_corpus_satisfies_public_suite_schema() -> None:
    schema = json.loads(Path("schemas/model-evaluation-suite.schema.json").read_text())
    corpus = json.loads(Path("benchmarks/model-evaluation/reference-v1.json").read_text())
    Draft202012Validator(schema).validate(corpus)
