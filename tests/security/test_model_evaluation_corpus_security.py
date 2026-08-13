import json
from pathlib import Path

import pytest

from nexus_os.model_evaluation import ModelEvaluationError, load_benchmark_suite
from tests.unit.test_model_evaluation_corpus import CORPUS, digest


def test_duplicate_json_keys_and_non_finite_values_are_rejected(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"schema_version":"1.0","schema_version":"1.0","suite_version":"x","cases":[]}'
    )
    with pytest.raises(ModelEvaluationError, match="duplicate"):
        load_benchmark_suite(duplicate, expected_digest=digest())

    non_finite = tmp_path / "non-finite.json"
    non_finite.write_text('{"schema_version":"1.0","suite_version":"x","cases":NaN}')
    with pytest.raises(ModelEvaluationError, match="non-finite"):
        load_benchmark_suite(non_finite, expected_digest=digest())


def test_secret_like_prompt_and_oversized_corpus_are_rejected(tmp_path: Path) -> None:
    document = json.loads(CORPUS.read_text())
    document["cases"][0]["prompt"] = "Bearer abcdefghijklmnop"
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps(document))
    with pytest.raises(ModelEvaluationError, match="secret-like"):
        load_benchmark_suite(secret, expected_digest=digest())

    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b" " * 1_000_001)
    with pytest.raises(ModelEvaluationError, match="oversized"):
        load_benchmark_suite(oversized, expected_digest=digest())


def test_anchor_file_contains_only_one_canonical_digest() -> None:
    anchor = Path("benchmarks/model-evaluation/reference-v1.sha256").read_text()
    assert anchor == digest() + "\n"
