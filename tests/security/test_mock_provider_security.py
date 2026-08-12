import asyncio
import inspect

import pytest

import nexus_os.mock_provider as mock_provider
from nexus_os.domain import RunId, TaskId, TraceId
from nexus_os.mock_provider import DeterministicMockAdapter
from nexus_os.providers import AdapterError, ProviderTask


def test_mock_rejects_unconfigured_operation_without_echoing_input() -> None:
    adapter = DeterministicMockAdapter(strict_operations=True)
    item = ProviderTask(
        "provider-task-1",
        RunId.parse("00000000-0000-4000-8000-000000000001"),
        TaskId("build_task"),
        TraceId("1" * 32),
        "unconfigured",
        {"prompt": "DO NOT LEAK THIS"},
        60,
    )
    with pytest.raises(AdapterError) as caught:
        asyncio.run(adapter.run(item))
    assert "DO NOT LEAK THIS" not in str(caught.value)


def test_mock_adapter_has_no_vendor_or_randomness_imports() -> None:
    source = inspect.getsource(mock_provider)
    for forbidden in ("import openai", "import anthropic", "import random", "import secrets"):
        assert forbidden not in source
