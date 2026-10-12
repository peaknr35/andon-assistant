"""Pull sync: read upcoming events from enabled cloud calendars into the local store,
de-duplicated by each provider's event id. Best-effort; never raises."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from ..memory import store
from ..tools import google_calendar, outlook_calendar

logger = logging.getLogger(__name__)

PULL_DAYS_BACK = 1
PULL_DAYS_AHEAD = 60


def _window() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return ((now - timedelta(days=PULL_DAYS_BACK)).strftime(fmt),
            (now + timedelta(days=PULL_DAYS_AHEAD)).strftime(fmt))


def any_enabled() -> bool:
    return google_calendar.is_enabled() or outlook_calendar.is_enabled()


def sync_once() -> dict:
    """Pull from every enabled provider and upsert locally. Returns per-provider counts."""
    lo, hi = _window()
    counts: dict[str, int] = {}
    for name, mod in (("google", google_calendar), ("outlook", outlook_calendar)):
        if not mod.is_enabled():
            continue
        n = 0
        try:
            for ev in mod.list_events(lo, hi):
                if not ev.get("external_id") or not ev.get("start"):
                    continue
                store.upsert_event_by_external_id(
                    name, ev["external_id"], ev["title"], ev["start"],
                    ev.get("end"), ev.get("notes"),
                )
                n += 1
        except Exception as exc:  # defensive; provider modules already swallow their own
            logger.warning("%s calendar sync failed: %s", name, exc)
        counts[name] = n
    return counts
