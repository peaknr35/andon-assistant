"""Calendar sync tests (all offline): providers disabled by default, dedup upsert,
pull sync with a fake provider, and the local-only create path."""
import asyncio

import pytest

from app.config import get_settings
from app.tools import google_calendar, outlook_calendar


def test_outlook_disabled_by_default(monkeypatch):
    monkeypatch.delenv("APP_OUTLOOK_CALENDAR", raising=False)
    assert outlook_calendar.is_enabled() is False
    # disabled -> no msal/network, returns None / []
    assert outlook_calendar.create_event("Lunch", "2026-10-10T12:00") is None
    assert outlook_calendar.list_events("2026-10-01T00:00:00Z", "2026-12-01T00:00:00Z") == []


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "state.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_upsert_dedup(temp_db):
    from app.memory import store
    a = store.upsert_event_by_external_id("google", "G1", "Standup", "2026-10-13T09:00:00")
    b = store.upsert_event_by_external_id("google", "G1", "Standup (moved)", "2026-10-13T10:00:00")
    assert a == b  # same row updated, not duplicated
    rows = store.list_events()
    assert len([r for r in rows if r["title"].startswith("Standup")]) == 1
    assert any(r["start"] == "2026-10-13T10:00:00" for r in rows)


def test_sync_once_pulls_and_dedupes(temp_db, monkeypatch):
    from app.memory import store
    from app.services import calendar_sync

    fake = [
        {"external_id": "G1", "title": "Site visit", "start": "2026-10-20T08:00:00",
         "end": None, "notes": None},
        {"external_id": "G2", "title": "Audit", "start": "2026-10-21T08:00:00",
         "end": None, "notes": "annual"},
    ]
    monkeypatch.setattr(google_calendar, "is_enabled", lambda: True)
    monkeypatch.setattr(google_calendar, "list_events", lambda lo, hi: fake)
    monkeypatch.setattr(outlook_calendar, "is_enabled", lambda: False)

    counts = calendar_sync.sync_once()
    assert counts.get("google") == 2
    assert len(store.list_events()) == 2
    # a second pull updates in place, never duplicates
    calendar_sync.sync_once()
    assert len(store.list_events()) == 2


def test_calendar_create_local_only(temp_db, monkeypatch):
    from app.tools.calendar import make_calendar_create
    monkeypatch.setattr(google_calendar, "is_enabled", lambda: False)
    monkeypatch.setattr(outlook_calendar, "is_enabled", lambda: False)
    out = asyncio.run(make_calendar_create().func("PM check", "2026-10-13T07:00:00"))
    assert "Created event" in out
    assert "synced" not in out  # nothing enabled -> no sync suffix
