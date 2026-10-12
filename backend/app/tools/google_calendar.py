"""Optional two-way Google Calendar sync. OFF unless APP_GOOGLE_CALENDAR=1 and a token
file (APP_GOOGLE_TOKEN_FILE) is configured. Generate the token once with
scripts/google_auth.py. Requires the optional extras:
    pip install google-api-python-client google-auth google-auth-oauthlib
The local SQLite calendar stays the source of truth; this mirrors events out (create) and
reads them back in (list) for the pull sync. Never raises -- callers treat None/[] as
"not synced".
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def is_enabled() -> bool:
    return os.getenv("APP_GOOGLE_CALENDAR", "") == "1"


def _timezone() -> str:
    return os.getenv("APP_CALENDAR_TIMEZONE", "UTC")


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_file = os.getenv("APP_GOOGLE_TOKEN_FILE", "")
    if not token_file:
        raise RuntimeError("APP_GOOGLE_TOKEN_FILE is not set")
    creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    if (not creds.valid) and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def create_event(title: str, start: str, end: Optional[str] = None,
                 notes: Optional[str] = None) -> Optional[str]:
    """Create a Google Calendar event; return its Google id, or None if disabled/failed."""
    if not is_enabled():
        return None
    try:
        service = _service()
        tz = _timezone()
        body = {
            "summary": title,
            "description": notes or "",
            "start": {"dateTime": start, "timeZone": tz},
            "end": {"dateTime": end or start, "timeZone": tz},
        }
        ev = service.events().insert(calendarId="primary", body=body).execute()
        return ev.get("id")
    except Exception as exc:  # optional + best-effort; never breaks the local path
        logger.warning("google calendar create failed: %s", exc)
        return None


def list_events(time_min: str, time_max: str) -> list[dict]:
    """Return Google events in [time_min, time_max] (RFC3339, e.g. 2026-10-12T00:00:00Z).
    Each item: {external_id, title, start, end, notes}. [] if disabled/failed."""
    if not is_enabled():
        return []
    try:
        service = _service()
        resp = service.events().list(
            calendarId="primary", timeMin=time_min, timeMax=time_max,
            singleEvents=True, orderBy="startTime", maxResults=100,
        ).execute()
        out: list[dict] = []
        for ev in resp.get("items", []):
            s = (ev.get("start") or {})
            e = (ev.get("end") or {})
            start = s.get("dateTime") or s.get("date")
            if not start:
                continue
            out.append({
                "external_id": ev.get("id"),
                "title": ev.get("summary") or "(no title)",
                "start": start,
                "end": e.get("dateTime") or e.get("date"),
                "notes": ev.get("description") or None,
            })
        return out
    except Exception as exc:
        logger.warning("google calendar list failed: %s", exc)
        return []
