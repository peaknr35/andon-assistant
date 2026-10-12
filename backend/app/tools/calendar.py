"""Local calendar tools -- events live in the SQLite events table (local-first).
If Google and/or Outlook sync is enabled, new events are mirrored OUT (create) and
existing cloud events are pulled IN before a list; the local store stays the source of truth."""
from __future__ import annotations

import asyncio

from . import google_calendar, outlook_calendar
from .base import ToolSpec


def make_calendar_create() -> ToolSpec:
    async def calendar_create(title: str, start: str, end: str = "", notes: str = "") -> str:
        """Create a calendar event. start/end are ISO-8601 datetimes, e.g. 2026-10-10T09:00."""
        from ..memory import store
        gid, oid = await asyncio.gather(
            asyncio.to_thread(google_calendar.create_event, title, start, end or None, notes or None),
            asyncio.to_thread(outlook_calendar.create_event, title, start, end or None, notes or None),
        )
        eid = await asyncio.to_thread(
            store.add_event, title, start, end or None, notes or None, gid, oid
        )
        synced = [name for name, v in (("Google", gid), ("Outlook", oid)) if v]
        suffix = f" (synced to {', '.join(synced)})" if synced else ""
        return f"Created event #{eid}: {title} at {start}{suffix}"

    return ToolSpec("calendar_create", "Create a local calendar event.", calendar_create)


def make_calendar_list() -> ToolSpec:
    async def calendar_list(start: str = "", end: str = "") -> str:
        """List calendar events, optionally within an ISO-8601 date range."""
        from ..memory import store
        from ..services.calendar_sync import any_enabled, sync_once
        if any_enabled():
            await asyncio.to_thread(sync_once)
        rows = await asyncio.to_thread(store.list_events, start or None, end or None, 50)
        if not rows:
            return "No events."
        return "\n".join(
            f"#{e['id']} {e['start']} -- {e['title']}" + (f" (ends {e['end']})" if e["end"] else "")
            for e in rows
        )

    return ToolSpec("calendar_list", "List upcoming local calendar events.", calendar_list)
