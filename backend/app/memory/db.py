"""SQLite connection + schema init. One file, local-first.

Connections are opened per call (the calling thread owns them). The agent loop
runs DB work via asyncio.to_thread so it never blocks the event loop.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ..config import get_settings

_SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


def db_path() -> Path:
    s = get_settings()
    p = Path(s.db_path).expanduser() if s.db_path else Path.home() / ".assistant" / "state.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent schema upgrades for existing DBs (CREATE IF NOT EXISTS won't alter)."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(events)")}
    if "outlook_id" not in cols:
        conn.execute("ALTER TABLE events ADD COLUMN outlook_id TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_outlook ON events (outlook_id)")
    conn.commit()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(_SCHEMA)
    _migrate(conn)
    return conn
