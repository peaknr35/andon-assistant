"""Optional two-way Microsoft Outlook (Microsoft 365) calendar sync via Microsoft Graph.
OFF unless APP_OUTLOOK_CALENDAR=1 with an Entra (Azure AD) app registration. Generate the
token once with scripts/outlook_auth.py (device-code sign-in). Requires the optional extra:
    pip install msal
(httpx is already a dependency.) Local SQLite stays the source of truth; this mirrors events
out (create) and reads them back in (list). Never raises -- callers treat None/[] as "not
synced".
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

GRAPH = "https://graph.microsoft.com/v1.0"
SCOPES = ["Calendars.ReadWrite"]


def is_enabled() -> bool:
    return os.getenv("APP_OUTLOOK_CALENDAR", "") == "1"


def _timezone() -> str:
    return os.getenv("APP_CALENDAR_TIMEZONE", "UTC")


def _token() -> str:
    """Acquire an access token silently from the cached account. Raises on failure."""
    import msal

    client_id = os.getenv("APP_OUTLOOK_CLIENT_ID", "")
    tenant = os.getenv("APP_OUTLOOK_TENANT", "common")
    cache_file = os.getenv("APP_OUTLOOK_TOKEN_CACHE", "")
    if not client_id or not cache_file:
        raise RuntimeError("APP_OUTLOOK_CLIENT_ID and APP_OUTLOOK_TOKEN_CACHE must be set")

    cache = msal.SerializableTokenCache()
    if os.path.exists(cache_file):
        cache.deserialize(open(cache_file, "r", encoding="utf-8").read())
    app = msal.PublicClientApplication(
        client_id, authority=f"https://login.microsoftonline.com/{tenant}", token_cache=cache
    )
    accounts = app.get_accounts()
    result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
    if not result or "access_token" not in result:
        raise RuntimeError("no cached Outlook token; run scripts/outlook_auth.py first")
    if cache.has_state_changed:
        with open(cache_file, "w", encoding="utf-8") as f:
            f.write(cache.serialize())
    return result["access_token"]


def create_event(title: str, start: str, end: Optional[str] = None,
                 notes: Optional[str] = None) -> Optional[str]:
    """Create an Outlook event; return its Graph id, or None if disabled/failed."""
    if not is_enabled():
        return None
    try:
        token = _token()
        tz = _timezone()
        body = {
            "subject": title,
            "body": {"contentType": "text", "content": notes or ""},
            "start": {"dateTime": start, "timeZone": tz},
            "end": {"dateTime": end or start, "timeZone": tz},
        }
        r = httpx.post(f"{GRAPH}/me/events", json=body,
                       headers={"Authorization": f"Bearer {token}"}, timeout=20.0)
        r.raise_for_status()
        return r.json().get("id")
    except Exception as exc:  # optional + best-effort; never breaks the local path
        logger.warning("outlook calendar create failed: %s", exc)
        return None


def list_events(time_min: str, time_max: str) -> list[dict]:
    """Return Outlook events in [time_min, time_max] (ISO-8601). Each item:
    {external_id, title, start, end, notes}. [] if disabled/failed."""
    if not is_enabled():
        return []
    try:
        token = _token()
        params = {"startDateTime": time_min, "endDateTime": time_max,
                  "$orderby": "start/dateTime", "$top": "100"}
        r = httpx.get(f"{GRAPH}/me/calendarView", params=params,
                      headers={"Authorization": f"Bearer {token}",
                               "Prefer": f'outlook.timezone="{_timezone()}"'}, timeout=20.0)
        r.raise_for_status()
        out: list[dict] = []
        for ev in r.json().get("value", []):
            start = (ev.get("start") or {}).get("dateTime")
            if not start:
                continue
            out.append({
                "external_id": ev.get("id"),
                "title": ev.get("subject") or "(no title)",
                "start": start,
                "end": (ev.get("end") or {}).get("dateTime"),
                "notes": (ev.get("body") or {}).get("content") or None,
            })
        return out
    except Exception as exc:
        logger.warning("outlook calendar list failed: %s", exc)
        return []
