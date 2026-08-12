import inspect

import nexus_os.providers as providers


def test_core_provider_sdk_has_no_vendor_imports() -> None:
    source = inspect.getsource(providers)
    for vendor in ("openai", "anthropic", "claude", "google.generativeai"):
        assert f"import {vendor}" not in source
