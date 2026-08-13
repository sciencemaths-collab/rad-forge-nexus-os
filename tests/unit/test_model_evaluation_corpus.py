import json
from pathlib import Path

import pytest

from nexus_os.model_evaluation import ModelEvaluationError, load_benchmark_suite
from nexus_os.model_qualification import EvaluationCategory

CORPUS = Path("benchmarks/model-evaluation/reference-v1.json")
ANCHOR = Path("benchmarks/model-evaluation/reference-v1.sha256")


def digest() -> str:
    return ANCHOR.read_text().strip()


def test_reference_corpus_loads_from_trusted_digest_with_balanced_coverage() -> None:
    suite = load_benchmark_suite(CORPUS, expected_digest=digest())
    assert suite.suite_version == "reference-v1"
    assert suite.corpus_digest == digest()
    assert len(suite.cases) == 14
    assert {
        category: sum(case.category is category for case in suite.cases)
        for category in EvaluationCategory
    } == {category: 2 for category in EvaluationCategory}


def test_invalid_anchor_and_tampered_corpus_are_rejected(tmp_path: Path) -> None:
    with pytest.raises(ModelEvaluationError, match="expected corpus digest"):
        load_benchmark_suite(CORPUS, expected_digest="not-a-digest")
    document = json.loads(CORPUS.read_text())
    document["cases"][0]["prompt"] += " changed"
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(document))
    with pytest.raises(ModelEvaluationError, match="trusted anchor"):
        load_benchmark_suite(changed, expected_digest=digest())


def test_unknown_fields_and_insufficient_category_depth_are_rejected(tmp_path: Path) -> None:
    document = json.loads(CORPUS.read_text())
    document["unexpected"] = True
    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps(document))
    with pytest.raises(ModelEvaluationError, match="fields"):
        load_benchmark_suite(unknown, expected_digest=digest())

    document = json.loads(CORPUS.read_text())
    document["cases"] = [
        case for case in document["cases"] if case["case_id"] != "planning.ordered_workflow"
    ]
    shallow = tmp_path / "shallow.json"
    shallow.write_text(json.dumps(document))
    with pytest.raises(ModelEvaluationError, match="at least two"):
        load_benchmark_suite(shallow, expected_digest="sha256:" + "0" * 64)
