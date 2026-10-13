# backend/app/tools -- the tool registry (agent "nodes")

One job: the practical things the agent can do. Each tool is a typed async function
returning a string observation; the SAME function feeds the manual backend (prompt
describes it) and PydanticAI (infers its schema). Mirrors ../../../_shared/tools.md.

## What's here
- `base.py` -- `ToolSpec`, `ToolResult`, `ToolRegistry` (+ `manual_catalog()`).
- `registry.py` -- `build_registry(client)` assembles the set for one turn.
- `web_search.py` -- wraps `services/search.web_search`.
- `deep_research.py` -- fast multi-source web research -> cited summary (parallel searches
  + one writeup; the full progressive pipeline lives in `services/research.py`).
- `calendar.py` -- `calendar_create` / `calendar_list` over the local events table.
  On create it mirrors OUT to Google and Outlook (when enabled); before a list it pulls
  cloud events IN. Local SQLite stays the source of truth.
- `google_calendar.py` -- optional two-way Google sync (create + list + token refresh),
  `APP_GOOGLE_CALENDAR=1`. Lazy-imports the Google libs; best-effort, never raises.
- `outlook_calendar.py` -- optional two-way Outlook sync via Microsoft Graph (MSAL + httpx),
  `APP_OUTLOOK_CALENDAR=1`. Lazy-imports msal; best-effort, never raises.
- `file_tools.py` -- `file_read` / `file_write`, sandboxed to `APP_FILE_ROOT`
  (toggle `APP_FILE_UNRESTRICTED=1` to widen; path-escape check always on).
- `memory_tools.py` -- `remember` / `recall` (explicit long-term memory).

## Rules
- A tool returns a short string the model can read; it never raises to the loop.
- Tools needing the LLM (deep_research) get the client via `build_registry`.
- Optional integrations (Google/Outlook) import their libs lazily and degrade to a no-op.
  The calendar tools are the agent's only surface -- sync is transparent.

## Where to add a tool
See `../../../_templates/new-tool.md`.

## Links
- Tool contract: `../../../_shared/tools.md` . Calendar sync: `../../../_shared/calendar-sync.md`
- Pull-sync service: `../services/calendar_sync.py` . Parent: `../CONTEXT.md`
