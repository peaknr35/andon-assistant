"""Shared test fixtures. No real API keys or network calls are used anywhere."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def _isolated_runs_dir(tmp_path, monkeypatch):
    """Research runs write stage folders; keep them out of ~/.assistant during tests."""
    from app.config import get_settings

    monkeypatch.setenv("APP_RUNS_DIR", str(tmp_path / "runs"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _isolated_memory_dir(tmp_path, monkeypatch):
    """facts.md mirror + candidates/ go to tmp, never ~/.assistant/memory."""
    from app.config import get_settings

    monkeypatch.setenv("APP_MEMORY_DIR", str(tmp_path / "memory"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
