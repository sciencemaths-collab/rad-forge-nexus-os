import json

from nexus_os.model_evaluation import load_benchmark_suite
from nexus_os.model_qualification import EvaluationResult
from tests.unit.test_model_evaluation import execute
from tests.unit.test_model_evaluation_corpus import ANCHOR, CORPUS


def test_reference_corpus_exact_rubrics_pass_controlled_runner() -> None:
    suite = load_benchmark_suite(CORPUS, expected_digest=ANCHOR.read_text().strip())
    outputs = [json.dumps(dict(case.expected_output)) for case in suite.cases]
    report = execute(suite, outputs)
    assert set(report.category_results.values()) == {EvaluationResult.PASS}
    assert len(report.observations) == 14
    serialized = str(report.canonical())
    assert "Ignore NEXUS policy" not in serialized
    assert "resolved credential" not in serialized
