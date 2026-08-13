import asyncio
import os

import pytest

from nexus_os.cloud_http_transport import AnthropicHTTPTransport, OpenAIHTTPTransport


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("RAD_LIVE_OPENAI") != "1",
    reason="set RAD_LIVE_OPENAI=1 for explicit credentialed smoke test",
)
def test_live_openai_model_discovery() -> None:
    key = os.environ["OPENAI_API_KEY"]
    models = asyncio.run(OpenAIHTTPTransport(timeout_seconds=30).list_models(key))
    assert models


@pytest.mark.live
@pytest.mark.skipif(
    os.environ.get("RAD_LIVE_ANTHROPIC") != "1",
    reason="set RAD_LIVE_ANTHROPIC=1 for explicit credentialed smoke test",
)
def test_live_anthropic_model_discovery() -> None:
    key = os.environ["ANTHROPIC_API_KEY"]
    models = asyncio.run(AnthropicHTTPTransport(timeout_seconds=30).list_models(key))
    assert models
