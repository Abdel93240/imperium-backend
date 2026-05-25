from __future__ import annotations

import os

import pytest


def require_test_database_url(test_scope: str) -> str:
    database_url = os.environ.get("IMPERIUM_TEST_DATABASE_URL")
    if database_url:
        return database_url

    message = f"IMPERIUM_TEST_DATABASE_URL not set; skipping {test_scope}."
    if os.environ.get("CI"):
        pytest.fail(f"{message} CI must run PostgreSQL invariant tests.")
    pytest.skip(message, allow_module_level=True)
