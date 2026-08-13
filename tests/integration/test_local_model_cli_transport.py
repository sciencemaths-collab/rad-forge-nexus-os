import asyncio
import io
import json
from pathlib import Path

from nexus_os.local_model_cli import run_local_model_cli
from nexus_os.loopback_http_transport import LoopbackHTTPTransport
from nexus_os.model_evaluation import load_benchmark_suite
from tests.unit.test_local_model_cli import arguments
from tests.unit.test_loopback_http_transport import Connection, Response
from tests.unit.test_model_evaluation_corpus import ANCHOR, CORPUS


class QueueFactory:
    def __init__(self) -> None:
        suite = load_benchmark_suite(CORPUS, expected_digest=ANCHOR.read_text().strip())
        self.connections = []
        for index, case in enumerate(suite.cases, start=1):
            payload = {
                "id": f"completion-{index}",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(dict(case.expected_output)),
                        },
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            }
            self.connections.append(Connection(Response(json.dumps(payload).encode())))

    def __call__(self, scheme, host, port, timeout):  # type: ignore[no-untyped-def]
        return self.connections.pop(0)


def test_operator_command_integrates_real_transport_adapter_corpus_and_report(
    tmp_path: Path,
) -> None:
    output = tmp_path / "manifest.json"
    queue = QueueFactory()

    def factory(sandbox):  # type: ignore[no-untyped-def]
        return LoopbackHTTPTransport(sandbox=sandbox, connection_factory=queue)

    code = asyncio.run(
        run_local_model_cli(
            arguments(output),
            stdout=io.StringIO(),
            stderr=io.StringIO(),
            transport_factory=factory,
        )
    )
    assert code == 0
    manifest = json.loads(output.read_text())
    assert set(manifest["report"]["category_results"].values()) == {"PASS"}
    assert queue.connections == []
