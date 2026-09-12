from dataclasses import dataclass

from tests.conftest import pytest_collection_modifyitems


@dataclass
class Item:
    name: str
    fixturenames: tuple[str, ...]


def test_browser_runtime_is_stably_scheduled_after_asyncio_users() -> None:
    items = [
        Item("browser-one", ("page",)),
        Item("unit-one", ()),
        Item("browser-two", ("browser",)),
        Item("unit-two", ("tmp_path",)),
    ]
    pytest_collection_modifyitems(items)
    assert [item.name for item in items] == [
        "unit-one",
        "unit-two",
        "browser-one",
        "browser-two",
    ]
