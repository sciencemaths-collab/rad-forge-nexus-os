"""Cross-suite lifecycle controls for third-party test runtimes."""

from __future__ import annotations

from typing import Any


def pytest_collection_modifyitems(items: list[Any]) -> None:
    """Run session-scoped synchronous Playwright tests after asyncio.run users.

    pytest-playwright keeps Playwright's synchronous event loop active until session
    teardown. Python 3.14 detects that loop when a later non-browser test calls
    ``asyncio.run``. Stable partitioning keeps all tests and assertions intact while
    ensuring the browser runtime owns the final portion of the test session.
    """
    non_browser = []
    browser = []
    for item in items:
        target = (
            browser
            if {"page", "browser", "playwright"}.intersection(item.fixturenames)
            else non_browser
        )
        target.append(item)
    items[:] = non_browser + browser
