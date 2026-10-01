"""NFR-013: CI lint/type/test gates need at least one collected test to be meaningful."""

import importlib

import pytest

MODULES = [
    "api",
    "models",
    "schemas",
    "services",
    "repositories",
    "finance",
    "providers",
    "rag",
    "citation",
    "ingestion",
    "tasks",
    "utils",
]


@pytest.mark.parametrize("module", MODULES)
def test_app_module_is_importable(module: str) -> None:
    assert importlib.import_module(f"app.{module}")
