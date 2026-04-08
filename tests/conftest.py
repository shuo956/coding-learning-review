from __future__ import annotations

from pathlib import Path

import pytest

from leetrevive.db import init_db


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Return a freshly initialised test database path."""
    path = tmp_path / "test.db"
    init_db(path)
    return path


@pytest.fixture(autouse=False)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    Set LEETREVIVE_DB_PATH so all db.get_db_path() calls in the process
    resolve to a temp file. Use this in command-level tests.
    """
    path = tmp_path / "test.db"
    init_db(path)
    monkeypatch.setenv("LEETREVIVE_DB_PATH", str(path))
    return path
