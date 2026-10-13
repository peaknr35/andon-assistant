# Tools (single source of truth)

A tool is a typed async function returning a string observation, wrapped in a
`ToolSpec` (`backend/app/tools/base.py`) and assembled by `build_registry`
(`backend/app/tools/registry.py`). The SAME function feeds both agent backends
(manual prompt-JSON + PydanticAI).

## Built-in tools
| tool | args | does |
|---|---|---|
| `web_search` | `query, max_results=5` | live web search (DuckDuckGo) |
| `deep_research` | `query` | multi-source web research -> cited summary |
| `remember` | `text` | save a fact to memory (explicit) |
| `recall` | `query` | search memory |
| `calendar_list` | `start="", end=""` | list local events (pulls cloud first when synced) |
| `calendar_create` | `title, start, end="", notes=""` | create a local event, mirror to cloud when synced |
| `file_read` | `path` | read a workspace text file (sandboxed) |
| `file_write` | `path, content` | write a workspace text file (sandboxed) |

## File safety
`file_read` / `file_write` resolve paths under `APP_FILE_ROOT`
(default `~/.assistant/workspace`). `APP_FILE_UNRESTRICTED=1` widens to the whole
filesystem; the path-escape check is always applied relative to the root otherwise.

## Calendar sync (optional, two-way, off by default)
`calendar_create` / `calendar_list` are the agent's only calendar surface; the local
SQLite `events` table is the source of truth. When a provider is enabled, create mirrors
OUT and list pulls IN -- transparently. A sync provider is a small module exposing
`is_enabled()`, `create_event(...) -> external_id|None`, and
`list_events(time_min, time_max) -> [...]`; best-effort, never raises. Providers today:
`google_calendar.py`, `outlook_calendar.py`. The pull + de-dup lives in
`services/calendar_sync.py`. Full setup + env flags: `calendar-sync.md`.

## Adding a tool
See `../_templates/new-tool.md`.
