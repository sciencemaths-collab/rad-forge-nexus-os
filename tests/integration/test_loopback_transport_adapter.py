import asyncio
import json
from pathlib import Path

from nexus_os.local_openai_adapter import LocalOpenAIAdapter
from nexus_os.loopback_http_transport import LoopbackHTTPTransport
from nexus_os.sandbox import WorkspaceSandbox
from nexus_os.secrets import SecretResolver
from tests.unit.test_local_openai_adapter import task
from tests.unit.test_loopback_http_transport import Connection, Response


def test_real_transport_boundary_integrates_with_local_adapter(tmp_path: Path) -> None:
    payload = {
        "id": "chatcmpl-real-boundary",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": "candidate"},
            }
        ],
        "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
    }
    connection = Connection(Response(json.dumps(payload).encode()))
    transport = LoopbackHTTPTransport(
        sandbox=WorkspaceSandbox(tmp_path, network_hosts=("127.0.0.1",)),
        connection_factory=lambda scheme, host, port, timeout: connection,
    )
    adapter = LocalOpenAIAdapter(
        base_url="http://127.0.0.1:11434/v1",
        model="fixture",
        credential=None,
        resolver=SecretResolver(),
        transport=transport,
    )
    item = task("real-transport-boundary")
    asyncio.run(adapter.run(item))
    result = asyncio.run(adapter.result(item.provider_task_id))
    assert result.metadata["output_text"] == "candidate"
    assert result.usage.total_tokens == 3
