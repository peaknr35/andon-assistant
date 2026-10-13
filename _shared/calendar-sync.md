# Calendar Sync (single source of truth)

Optional, two-way, **off by default**. The local SQLite `events` table is always the
source of truth; enabling a provider mirrors events OUT on create and pulls them IN on
list + on a timer. Human OAuth setup: `../docs/CALENDAR-SYNC.md`.

## Provider shape (every provider module mirrors this)
`backend/app/tools/<provider>_calendar.py` exposes:
- `is_enabled() -> bool` -- reads its `APP_*_CALENDAR` flag.
- `create_event(title, start, end, notes) -> external_id | None` -- push one event out.
- `list_events(time_min, time_max) -> [{external_id, title, start, end, notes}]` -- pull.

All are best-effort and **never raise** (callers treat `None` / `[]` as "not synced").
Providers today: `google_calendar.py` (Google Calendar API, lazy google libs),
`outlook_calendar.py` (Microsoft Graph via httpx + MSAL).

## Flow
- **Push:** `tools/calendar.py:calendar_create` calls each enabled provider's
  `create_event` (in threads) and stores the returned ids in `events.google_id` /
  `events.outlook_id`.
- **Pull:** `services/calendar_sync.py:sync_once()` lists each enabled provider's upcoming
  events and upserts them via `store.upsert_event_by_external_id` (dedup by cloud id).
  It runs before `calendar_list` and on a periodic loop in `main.py`
  (`APP_CALENDAR_SYNC_MINUTES`, default 15; the loop starts only when a provider is enabled).

## Env flags
| var | meaning |
|---|---|
| `APP_GOOGLE_CALENDAR=1` + `APP_GOOGLE_TOKEN_FILE` | enable Google (token from `scripts/google_auth.py`) |
| `APP_OUTLOOK_CALENDAR=1` + `APP_OUTLOOK_CLIENT_ID` / `APP_OUTLOOK_TENANT` / `APP_OUTLOOK_TOKEN_CACHE` | enable Outlook (token from `scripts/outlook_auth.py`) |
| `APP_CALENDAR_TIMEZONE` | IANA tz for created cloud events (default `UTC`) |
| `APP_CALENDAR_SYNC_MINUTES` | pull interval in minutes (default 15) |

## Secrets
`credentials.json`, `token.json`, `outlook_token.json` are gitignored and never committed.

## Change this together with
`tools/google_calendar.py`, `tools/outlook_calendar.py`, `tools/calendar.py`,
`services/calendar_sync.py`, `memory/schema.sql` (the id columns), and
`../docs/CALENDAR-SYNC.md`.
